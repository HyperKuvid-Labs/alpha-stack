from google import genai
from google.genai import types
from dotenv import load_dotenv
import re
import json
import os
import string
from gen_file import GENERATABLE_FILENAMES,GENERATABLE_FILES
from folder_tree import TreeNode
from prompt import software_blueprint_prompt,folder_structure_prompt,file_format_prompt
load_dotenv(dotenv_path='.env')
client=genai.Client()

_client = None

def get_client():
    """
    This function initializes the Google AI client but only does it once.
    This is the key to fixing the startup problem.
    """
    global _client
    if _client is None:
        print("Backend: Initializing Google AI client...")
        _client = genai.Client()
    return _client

# --- Your Functions (Modified to use get_client()) ---

def inital_software_blueprint(prompt:str)->str:
    "gives the high level software blueprint with title roles and features"
    client = get_client()
    chat=client.chats.create(model='gemini-2.5-pro',config=types.GenerateContentConfig(systemInstruction=software_blueprint_prompt))
    # response = client.models.generate_content(
    # model="gemini-2.5-pro",
    # contents = types.Content(role='user',parts=[types.Part.from_text(text=prompt)]),
    # config=types.GenerateContentConfig(systemInstruction=software_blueprint_prompt)
    # )
    response=chat.send_message(prompt)
    match = re.search(r'\{.*\}', response.text, re.DOTALL)
    if match:
        clean_json_str = match.group(0)
        try:
         data = json.loads(clean_json_str)
         print("avolodhan parsed !!!")
         print("Project Name:", data["projectDetails"]["projectName"], "\n")
         print("🔹 Features:")
         for feature in data.get("features", []):
                print(f"  - {feature['name']}:")
                for desc in feature["description"]:
                    print(f"      • {desc}")
         print()
         print("👥 User Roles:")
         for role in data.get("userRoles", []):
                print(f"  - {role['role']}")
                print(f"      Permissions: {role['permissions']}")
                print(f"      Responsibilities: {role['responsibilities']}")
         print()
         print("Tech Stack:")
         for section, details in data.get("techStack", {}).items():
                print(f"  - {section.capitalize()}:")
                if isinstance(details, dict):
                    for k, v in details.items():
                        print(f"      {k}: {v}")
                else:
                    print(f"      {details}")
         print()
         return data
        except json.JSONDecodeError as e:
            return ("Error decoding JSON:", e)
def folder_structure(project_overveiw:str):
    """generates the folder_structure for the project description"""
    
    response = client.models.generate_content(
    model="gemini-2.5-pro",
    contents = types.Content(role='user',parts=[types.Part.from_text(text=json.dumps(project_overveiw))
    ]),
    config=types.GenerateContentConfig(systemInstruction=folder_structure_prompt)
    )
    return response.text
def files_format(project_overveiw:str,folder_structure:str):
    """generates the json file of each output"""
    response = client.models.generate_content(
    model="gemini-2.5-pro",
    contents = types.Content(role='user',parts=[types.Part.from_text(text=json.dumps(project_overveiw))
    ,types.Part.from_text(text=json.dumps(folder_structure))]),
    config=types.GenerateContentConfig(systemInstruction=file_format_prompt)
    )
    return response.text

def generate_tree(resp: str, project_name: str = "root") -> TreeNode:
    content = resp.strip().replace('```', '').strip()
    lines = content.split('\n')
    stack = []
    root = TreeNode(project_name)

    for line in lines:
        if not line.strip():
            continue

        indent = 0
        temp_line = line

        while temp_line.startswith('│   ') or temp_line.startswith('    ') or temp_line.startswith('│ ') or temp_line.startswith('    '):
            temp_line = temp_line[4:]
            indent += 1

        name = line.strip()
        if '#' in name:
            name = name.split('#')[0].strip()
        name = name.replace('│', '').replace('├──', '').replace('└──', '').strip()

        if not name or name == project_name:
            continue

        node = TreeNode(name)

        if indent == 0:
            root.add_child(node)
            stack = [root, node]
        else:
            while len(stack) > indent + 1:
                stack.pop()

            if stack:
                stack[-1].add_child(node)
            stack.append(node)




def main():
    """
    Executes the main logic and returns the features and folder structure.
    """
    print("--- Starting Backend Process ---")
    user_prompt="""A tiny app where a user can add, view, and delete short text notes."""
    software_blueprint = inital_software_blueprint(user_prompt)
    folder_struc = folder_structure(software_blueprint)
    print(folder_struc)
    file_format=files_format(software_blueprint,folder_struc)
    print(file_format)
    # # Create the project files
    # project_name = software_blueprint["projectDetails"]["projectName"]
    # folder_tree = generate_tree(folder_struc, project_name)
    # create_project_structure(folder_tree, project_name,software_blueprint,folder_struc ,base_path)

    # # Extract only the features list
    # features = software_blueprint.get("features", [])

    # print("--- Backend Process Finished ---")
main()