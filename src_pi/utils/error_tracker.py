import os
import json
from typing import List, Dict, Optional
from datetime import datetime


class ErrorTracker:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.change_log: List[Dict] = []
        self.error_history: List[Dict] = []
        
    def log_change(self, file_path: str, change_description: str, 
                   error_context: Optional[str] = None, 
                   before_content: Optional[str] = None,
                   after_content: Optional[str] = None,
                   error: Optional[str] = None,
                   actions: Optional[List[str]] = None) -> None:
        rel_path = os.path.relpath(file_path, self.project_root) if os.path.isabs(file_path) else file_path
        
        error_msg = error or error_context
        
        change_entry = {
            "timestamp": datetime.now().isoformat(),
            "file": rel_path,
            "change_description": change_description,
            "error": error_msg,
            "actions": actions or [],
            "error_context": error_context,
            "has_content_snapshot": before_content is not None or after_content is not None
        }
        
        if before_content:
            change_entry["before_length"] = len(before_content)
        if after_content:
            change_entry["after_length"] = len(after_content)
            
        self.change_log.append(change_entry)
    
    def log_error(self, error_info: Dict) -> None:
        self.error_history.append({
            "timestamp": datetime.now().isoformat(),
            **error_info
        })
    
    def get_change_summary(self) -> str:
        if not self.change_log:
            return "No changes have been made yet."
        
        summary_lines = ["## Change Log Summary\n"]
        summary_lines.append("**IMPORTANT**: Review this list carefully. If you see the same error/file combination with the same fix attempted multiple times, that fix did NOT work and you MUST try a different approach.\n")
        
        attempts_by_key = {}
        for idx, entry in enumerate(self.change_log):
            error_key = f"{entry['file']}|{entry.get('error', entry.get('error_context', ''))[:100]}"
            action_key = '|'.join(entry.get('actions', []))
            full_key = f"{error_key}|{action_key}"
            
            if full_key not in attempts_by_key:
                attempts_by_key[full_key] = []
            attempts_by_key[full_key].append(idx)
        
        for idx, entry in enumerate(self.change_log):
            error_key = f"{entry['file']}|{entry.get('error', entry.get('error_context', ''))[:100]}"
            action_key = '|'.join(entry.get('actions', []))
            full_key = f"{error_key}|{action_key}"
            
            attempt_count = len(attempts_by_key[full_key])
            is_repeat = attempt_count > 1 and idx in attempts_by_key[full_key][:-1]
            
            if is_repeat:
                summary_lines.append(f"⚠️ **ATTEMPT {attempts_by_key[full_key].index(idx) + 1} of {attempt_count}** (THIS FIX DID NOT WORK - DO NOT REPEAT)")
            elif attempt_count > 1 and idx == attempts_by_key[full_key][-1]:
                summary_lines.append(f"⚠️ **ATTEMPT {attempt_count} of {attempt_count}** (Same fix attempted {attempt_count} times - FAILED)")
            
            summary_lines.append(
                f"- **{entry['file']}**: {entry['change_description']}"
            )
            if entry.get('error'):
                summary_lines.append(f"  - Error: {entry['error']}")
            elif entry.get('error_context'):
                summary_lines.append(f"  - Error context: {entry['error_context']}")
            if entry.get('actions'):
                summary_lines.append(f"  - Actions: {', '.join(entry['actions'])}")
            summary_lines.append("")
        
        return "\n".join(summary_lines)
    
    def get_recent_changes(self, file_path: Optional[str] = None, limit: int = 10) -> List[Dict]:
        changes = self.change_log
        if file_path:
            rel_path = os.path.relpath(file_path, self.project_root) if os.path.isabs(file_path) else file_path
            changes = [c for c in changes if c['file'] == rel_path]
        return changes[-limit:]
    
    def to_dict(self) -> Dict:
        return {
            "project_root": self.project_root,
            "total_changes": len(self.change_log),
            "total_errors": len(self.error_history),
            "change_log": self.change_log,
            "error_history": self.error_history
        }
    
    def save_to_file(self, file_path: str) -> None:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2)
    
    @classmethod
    def load_from_file(cls, file_path: str) -> 'ErrorTracker':
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        tracker = cls(data['project_root'])
        tracker.change_log = data.get('change_log', [])
        tracker.error_history = data.get('error_history', [])
        return tracker

