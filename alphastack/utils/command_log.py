import os
import json
from datetime import datetime
from typing import Dict, List, Optional


class CommandLogManager:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self.log_dir = os.path.join(project_root, ".alpha_stack")
        self.log_file = os.path.join(self.log_dir, "command_logs.json")
        self.commands: List[Dict] = []
        self.last_summary: Optional[str] = None
        
        if not os.path.exists(self.log_dir):
            os.makedirs(self.log_dir, exist_ok=True)
        
        self.load_from_file()
    
    def _count_tokens(self, text: str) -> int:
        if not text:
            return 0
        return len(text) // 4
    
    def log_command(self, command: str, description: str, success: bool, 
                   logs: str, returncode: int, executed_in: str):
        command_entry = {
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "description": description,
            "success": success,
            "logs": logs,
            "returncode": returncode,
            "executed_in": executed_in
        }
        
        self.commands.append(command_entry)
        self.save_to_file()
    
    def get_formatted_history_for_planning(self, max_tokens: int = 10000) -> str:
        if not self.commands and not self.last_summary:
            return ""
        
        formatted = "Command Execution History:\n\n"
        
        if self.last_summary:
            formatted += f"[Summarized older commands]\n{self.last_summary}\n\n"
        
        if self.commands:
            formatted += "[Last command - always full]\n"
            formatted += self._format_single_command(self.commands[-1])
        elif self.last_summary:
            return formatted.rstrip()
        
        if self.commands:
            total_tokens = sum(self._count_tokens(cmd.get("logs", "")) + 
                              self._count_tokens(cmd.get("command", "")) + 50 
                              for cmd in self.commands)
            
            if total_tokens <= max_tokens and not self.last_summary:
                return self._format_all_commands()
        
        return formatted
    
    def _format_all_commands(self) -> str:
        formatted = "Command Execution History:\n\n"
        for i, cmd in enumerate(self.commands):
            formatted += f"[Command {i+1}]\n"
            formatted += self._format_single_command(cmd)
            if i < len(self.commands) - 1:
                formatted += "\n"
        return formatted
    
    def _format_single_command(self, cmd: Dict) -> str:
        formatted = f"Command: {cmd.get('command', '')}\n"
        if cmd.get('description'):
            formatted += f"Description: {cmd.get('description')}\n"
        
        logs = cmd.get('logs', '')
        if len(logs) > 700:
            output_preview = logs[:500] + "\n... [truncated] ...\n" + logs[-200:]
        else:
            output_preview = logs
        
        formatted += f"Output:\n{output_preview}\n"
        
        if cmd.get('success'):
            formatted += "Status: PASSED\n"
        else:
            formatted += f"Status: FAILED (exit code: {cmd.get('returncode', -1)})\n"
        
        important = self._extract_important_info(logs, cmd.get('success'))
        if important:
            formatted += f"Important: {important}\n"
        
        return formatted
    
    def _extract_important_info(self, logs: str, success: bool) -> str:
        if not logs:
            return ""
        
        important_lines = []
        lines = logs.split('\n')
        
        error_keywords = ['error', 'failed', 'exception', 'traceback', 'fatal', 
                         'cannot', 'unable', 'missing', 'not found']
        
        for line in lines:
            line_lower = line.lower()
            if any(keyword in line_lower for keyword in error_keywords):
                important_lines.append(line[:100])
                if len(important_lines) >= 3:
                    break
        
        if important_lines:
            return " | ".join(important_lines)
        
        if success:
            success_keywords = ['passed', 'success', 'completed', 'ok']
            for line in lines[-10:]:
                line_lower = line.lower()
                if any(keyword in line_lower for keyword in success_keywords):
                    return line[:100]
        
        return ""
    
    def save_to_file(self):
        try:
            data = {
                "commands": self.commands,
                "last_summary": self.last_summary
            }
            with open(self.log_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception:
            pass
    
    def load_from_file(self):
        if not os.path.exists(self.log_file):
            self.commands = []
            self.last_summary = None
            return
        
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.commands = data.get("commands", [])
                self.last_summary = data.get("last_summary")
        except Exception:
            self.commands = []
            self.last_summary = None
    
    def get_token_count(self) -> int:
        return sum(self._count_tokens(cmd.get("logs", "")) + 
                   self._count_tokens(cmd.get("command", "")) + 50 
                   for cmd in self.commands)
    
    def clear(self):
        self.commands = []
        self.last_summary = None
        self.save_to_file()

