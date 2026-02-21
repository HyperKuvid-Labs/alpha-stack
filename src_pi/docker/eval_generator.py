import os
import json
import re
from typing import Dict, List, Optional
from ..utils.helpers import prime_intellect_client, clean_agent_output, retry_api_call
from ..utils.prompt_manager import PromptManager
from ..utils.error_tracker import ErrorTracker


def extract_file_summaries(metadata_dict: Dict) -> Dict[str, str]:
    summaries = {}
    for file_path, entries in metadata_dict.items():
        if entries and isinstance(entries, list):
            for entry in entries:
                if isinstance(entry, dict) and "description" in entry:
                    summaries[file_path] = entry["description"]
                    break
    return summaries



def extract_external_dependencies(metadata_dict: Dict, dependency_analyzer) -> List[Dict[str, str]]:
    external_deps = set()
    for file_path in metadata_dict.keys():
        if os.path.exists(file_path):
            deps = dependency_analyzer.get_dependency_details(file_path)
            for dep in deps:
                if isinstance(dep, dict) and dep.get("kind") == "external":
                    raw_dep = dep.get("raw", "")
                    if raw_dep:
                        external_deps.add(raw_dep)


    return [{"raw": dep, "kind": "external"} for dep in sorted(external_deps)]



class DockerTestFileGeneratorEval:
    def __init__(self, project_root: str, software_blueprint: Dict,
                 folder_structure: str, file_output_format: Dict,
                 metadata_dict: Dict, dependency_analyzer, model_name: str,
                 pm: Optional[PromptManager] = None, on_status=None):
        self.project_root = project_root
        self.software_blueprint = software_blueprint
        self.folder_structure = folder_structure
        self.file_output_format = file_output_format
        self.metadata_dict = metadata_dict
        self.dependency_analyzer = dependency_analyzer
        self.pm = pm or PromptManager(templates_dir="prompts")
        self.error_tracker = ErrorTracker(project_root)
        self.on_status = on_status
        self.model_name = model_name


    def _emit(self, event_type: str, message: str, **kwargs):
        if self.on_status:
            self.on_status(event_type, message, **kwargs)


    def _extract_metadata_context(self) -> Dict:
        file_summaries = extract_file_summaries(self.metadata_dict)
        external_deps = extract_external_dependencies(self.metadata_dict, self.dependency_analyzer)
        return {
            "file_summaries": file_summaries,
            "external_dependencies": external_deps
        }


    def generate_test_dockerfile_blueprint(self) -> List[Dict]:
        metadata_context = self._extract_metadata_context()


        prompt = self.pm.render("test_dockerfile_blueprint.j2",
            software_blueprint=self.software_blueprint,
            folder_structure=self.folder_structure,
            file_output_format=self.file_output_format,
            file_summaries=metadata_context["file_summaries"],
            external_dependencies=metadata_context["external_dependencies"],
            project_root=self.project_root
        )


        client = prime_intellect_client()


        messages = [
            {"role": "user", "content": prompt}
        ]


        completion = retry_api_call(
            client.chat.completions.create,
            model=self.model_name,
            messages=messages
        )


        resp = completion.choices[0].message.content
        response_text = resp.strip()


        json_match = re.search(r'\[.*\]', response_text, re.DOTALL)
        if json_match:
            blueprint = json.loads(json_match.group())
        else:
            blueprint = json.loads(response_text)


        if isinstance(blueprint, dict):
            blueprint = [blueprint]


        return blueprint


    def generate_test_files(self, blueprint: List[Dict]) -> List[str]:
        generated_files = []
        metadata_context = self._extract_metadata_context()


        for item in blueprint:
            if item.get("type") != "test_file":
                continue


            target_file = item.get("target_file", "")
            test_file_path = item.get("test_file_path", "")


            if not target_file or not test_file_path:
                continue


            abs_test_path = os.path.join(self.project_root, test_file_path)
            os.makedirs(os.path.dirname(abs_test_path), exist_ok=True)


            target_metadata = None
            abs_target_file = os.path.abspath(os.path.join(self.project_root, target_file)) if not os.path.isabs(target_file) else target_file


            for file_path, entries in self.metadata_dict.items():
                if os.path.abspath(file_path) == abs_target_file:
                    if entries and isinstance(entries, list):
                        target_metadata = entries[0] if entries else None
                    break


            prompt = self.pm.render("test_file_generation.j2",
                software_blueprint=self.software_blueprint,
                folder_structure=self.folder_structure,
                file_output_format=self.file_output_format,
                target_file=target_file,
                target_file_metadata=target_metadata,
                test_file_path=test_file_path,
                external_dependencies=metadata_context["external_dependencies"],
                project_root=self.project_root
            )


            client = prime_intellect_client()


            messages = [
                {"role": "user", "content": prompt}
            ]


            completion = retry_api_call(
                client.chat.completions.create,
                model=self.model_name,
                messages=messages
            )


            resp = completion.choices[0].message.content
            test_content = clean_agent_output(resp)


            with open(abs_test_path, 'w', encoding='utf-8') as f:
                f.write(test_content)


            if abs_test_path not in self.metadata_dict:
                self.metadata_dict[abs_test_path] = []


            self.metadata_dict[abs_test_path].append({
                "description": item.get("description", f"Test file for {target_file}")
            })


            generated_files.append(abs_test_path)


        return generated_files


    def generate_dockerfile(self) -> bool:
        metadata_context = self._extract_metadata_context()


        prompt = self.pm.render("dockerfile_generation.j2",
            software_blueprint=self.software_blueprint,
            folder_structure=self.folder_structure,
            file_output_format=self.file_output_format,
            file_summaries=metadata_context["file_summaries"],
            external_dependencies=metadata_context["external_dependencies"],
            project_root=self.project_root
        )


        client = prime_intellect_client()


        messages = [
            {"role": "user", "content": prompt}
        ]


        completion = retry_api_call(
            client.chat.completions.create,
            model=self.model_name,
            messages=messages
        )


        resp = completion.choices[0].message.content


        dockerfile_content = resp.strip()


        if dockerfile_content.startswith('```'):
            lines = dockerfile_content.split('\n')
            if len(lines) > 1:
                dockerfile_content = '\n'.join(lines[1:])
                if dockerfile_content.endswith('```'):
                    dockerfile_content = dockerfile_content[:-3].rstrip()


        dockerfile_path = os.path.join(self.project_root, "Dockerfile")
        with open(dockerfile_path, 'w', encoding='utf-8') as f:
            f.write(dockerfile_content)


        self.error_tracker.log_change(
            file_path=dockerfile_path,
            change_description="Generated Dockerfile from project metadata",
            error_context="Dockerfile generation phase",
            actions=["generate_dockerfile"]
        )


        return True


    def resolve_test_dependencies(self, test_files: List[str]) -> Dict:
        if not test_files:
            return {"success": True, "resolved": 0}


        for test_file in test_files:
            if os.path.exists(test_file):
                try:
                    with open(test_file, 'r', encoding='utf-8', errors='ignore') as f:
                        content = f.read()
                    self.dependency_analyzer.add_file(test_file, content, self.folder_structure)
                except Exception:
                    pass


        resolved_count = 0
        for test_file in test_files:
            deps = self.dependency_analyzer.get_dependency_details(test_file)
            internal_deps = [d for d in deps if d.get("kind") == "internal" and d.get("path")]


            if internal_deps:
                resolved_count += len(internal_deps)


        return {"success": True, "resolved": resolved_count}


    def generate_all(self) -> Dict:
        results = {
            "blueprint": None,
            "test_files": [],
            "dockerfile": False,
            "dependency_resolution": None,
            "success": False
        }


        try:
            blueprint = self.generate_test_dockerfile_blueprint()
            results["blueprint"] = blueprint


            test_files = self.generate_test_files(blueprint)
            results["test_files"] = test_files


            dockerfile_success = self.generate_dockerfile()
            results["dockerfile"] = dockerfile_success


            dep_results = self.resolve_test_dependencies(test_files)
            results["dependency_resolution"] = dep_results


            results["success"] = dockerfile_success and len(test_files) > 0


        except Exception:
            pass


        return results
