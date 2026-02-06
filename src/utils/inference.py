import os
import json
import time
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


def retry_api_call(func, *args, max_retries: int = 10, **kwargs):
    """Retry API call with exponential backoff"""
    attempt = 1
    while attempt <= max_retries:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries:
                raise  # Re-raise on final attempt
            wait_time = min(0.5 * (2 ** (attempt - 1)), 10)  # Exponential backoff, max 10s
            time.sleep(wait_time)
            attempt += 1

# Registry for providers
_PROVIDER_REGISTRY = {}


def register_provider(name: str):
    """Decorator to register a provider class"""
    def decorator(cls):
        _PROVIDER_REGISTRY[name] = cls
        return cls
    return decorator


class InferenceProvider(ABC):
    """Base class for inference providers"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._client = None
    @property
    def model(self) -> str:
        return self.config.get("model")
    @property
    def api_key(self) -> Optional[str]:
        return self.config.get("api_key")
    
    @abstractmethod
    def get_client(self):
        """Get the client instance"""
        pass
    
    @abstractmethod
    def format_tools(self, tool_definitions: List[Dict]) -> Any:
        """Convert tool definitions to provider-specific format"""
        pass
    
    @abstractmethod
    def call_model(self, messages: List[Dict], tools: Any = None, **kwargs) -> Any:
        """Make API call to the model"""
        pass
    
    @abstractmethod
    def extract_function_calls(self, response: Any) -> List[Dict[str, Any]]:
        """Extract function calls from response"""
        pass
    
    @abstractmethod
    def create_function_response(self, function_name: str, result: Dict[str, Any], call_id: Optional[str] = None) -> Any:
        """Create function response in provider format"""
        pass
    
    @abstractmethod
    def extract_text(self, response: Any) -> str:
        """Extract text content from response"""
        pass

    @abstractmethod
    def create_initial_message(self, prompt: str) -> List:
        """Create initial message list with the given prompt in provider-specific format"""
        pass

    @abstractmethod
    def accumulate_messages(self, messages: List, response: Any, function_responses: List) -> None:
        """
        Accumulate tool call response and function results into message history.
        Modifies messages list in place.

        Args:
            messages: The message history list to append to
            response: The model's response containing tool calls
            function_responses: List of function response objects from create_function_response
        """
        pass


@register_provider("google")
class GoogleProvider(InferenceProvider):
    """Google Gemini provider using python-genai"""
    def get_client(self):
        if self._client is None:
            from google import genai
            from ..config import get_api_key
            api_key = self.api_key or get_api_key()
            self._client = genai.Client(api_key=api_key)
        return self._client
    
    def format_tools(self, tool_definitions: List[Dict]) -> Any:
        from google.genai import types
        
        function_declarations = []
        for tool_def in tool_definitions:
            function_declarations.append(
                types.FunctionDeclaration(
                    name=tool_def["name"],
                    description=tool_def["description"],
                    parameters=self._convert_schema(tool_def["parameters"])
                )
            )
        return types.Tool(function_declarations=function_declarations)
    
    def _convert_schema(self, schema: Dict) -> Any:
        from google.genai import types
        
        properties = {}
        type_map = {
            "string": types.Type.STRING,
            "integer": types.Type.INTEGER,
            "number": types.Type.NUMBER,
            "boolean": types.Type.BOOLEAN,
            "array": types.Type.ARRAY,
            "object": types.Type.OBJECT
        }
        
        for prop_name, prop_def in schema.get("properties", {}).items():
            prop_type = type_map.get(prop_def["type"].lower(), types.Type.STRING)
            properties[prop_name] = types.Schema(
                type=prop_type,
                description=prop_def.get("description", "")
            )
        
        return types.Schema(
            type=types.Type.OBJECT,
            properties=properties,
            required=schema.get("required", [])
        )
    
    def call_model(self, messages: List, tools: Any = None, **kwargs) -> Any:
        from google.genai import types

        contents = []
        for msg in messages:
            # If already a Content object (from agentic loop), use directly
            if isinstance(msg, types.Content):
                contents.append(msg)
            # If it's a GenerateContentResponse (model response), extract its content
            elif hasattr(msg, 'candidates') and msg.candidates:
                # This is a response object - extract the content from first candidate
                if msg.candidates[0].content:
                    contents.append(msg.candidates[0].content)
            else:
                # Convert dict to Content
                contents.append(
                    types.Content(
                        role=msg.get("role", "user"),
                        parts=[types.Part.from_text(text=msg.get("content", ""))]
                    )
                )

        config_kwargs = {}
        if tools:
            config_kwargs["tools"] = [tools]
            config_kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)

        config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

        call_kwargs = {
            "model": self.model,
            "contents": contents,
        }
        if config:
            call_kwargs["config"] = config

        # Add optional params
        for param in ["temperature", "max_output_tokens", "top_p", "top_k"]:
            if param in kwargs:
                call_kwargs[param] = kwargs[param]

        return retry_api_call(
            self.get_client().models.generate_content,
            **call_kwargs
        )
    
    def extract_function_calls(self, response: Any) -> List[Dict[str, Any]]:
        if not hasattr(response, 'function_calls') or not response.function_calls:
            return []
        
        function_calls = []
        for fc in response.function_calls:
            args = fc.args if isinstance(fc.args, dict) else (
                fc.args.__dict__ if hasattr(fc.args, '__dict__') else {}
            )
            function_calls.append({
                "name": fc.name,
                "args": args
            })
        return function_calls
    
    def create_function_response(self, function_name: str, result: Dict[str, Any], call_id: Optional[str] = None) -> Any:
        from google.genai import types
        return types.Part.from_function_response(name=function_name, response=result)
    
    def extract_text(self, response: Any) -> str:
        return response.text.strip() if hasattr(response, 'text') else ""

    def create_initial_message(self, prompt: str) -> List:
        from google.genai import types
        return [
            types.Content(role='user', parts=[types.Part.from_text(text=prompt)])
        ]

    def accumulate_messages(self, messages: List, response: Any, function_responses: List) -> None:
        from google.genai import types
        # Append model response (contains function calls) and tool results
        tool_content = types.Content(role='function', parts=function_responses)
        messages.append(response)  # Model's response with tool calls
        messages.append(tool_content)  # Tool results


@register_provider("openrouter")
class OpenRouterProvider(InferenceProvider):
    """OpenRouter provider (OpenAI-compatible)"""
    
    def get_client(self):
        if self._client is None:
            from openai import OpenAI
            api_key = self.api_key or os.getenv("OPENROUTER_API_KEY")
            base_url = self.config.get("base_url", "https://openrouter.ai/api/v1")
            
            # Add default headers for OpenRouter
            default_headers = {
                "HTTP-Referer": "https://pradheep.dev",
                "X-Title": "Alphastack",
            }
            
            self._client = OpenAI(
                api_key=api_key,
                base_url=base_url,
                default_headers=default_headers
            )
        return self._client
    
    def format_tools(self, tool_definitions: List[Dict]) -> List[Dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool_def["name"],
                    "description": tool_def["description"],
                    "parameters": tool_def["parameters"]
                }
            }
            for tool_def in tool_definitions
        ]
    
    def call_model(self, messages: List[Dict], tools: List[Dict] = None, **kwargs) -> Any:
        
        call_kwargs = {
            "model": self.model,
            "messages": messages,
        }
        
        if tools:
            call_kwargs["tools"] = tools
        
        # Add optional params
        for param in ["temperature", "max_tokens", "top_p"]:
            if param in kwargs:
                call_kwargs[param] = kwargs[param]
        
        return retry_api_call(
            self.get_client().chat.completions.create,
            **call_kwargs
        )
    
    def extract_function_calls(self, response: Any) -> List[Dict[str, Any]]:
        function_calls = []
        if hasattr(response, 'choices') and response.choices:
            message = response.choices[0].message
            if hasattr(message, 'tool_calls') and message.tool_calls:
                for tool_call in message.tool_calls:
                    if tool_call.type == "function":
                        args = tool_call.function.arguments
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except json.JSONDecodeError:
                                args = {}
                        elif not isinstance(args, dict):
                            args = {}
                        
                        function_calls.append({
                            "name": tool_call.function.name,
                            "args": args,
                            "id": tool_call.id
                        })
        return function_calls
    
    def create_function_response(self, function_name: str, result: Dict[str, Any], call_id: Optional[str] = None) -> Any:
        return {
            "role": "tool",
            "tool_call_id": call_id,
            "content": json.dumps(result) if not isinstance(result, str) else result
        }
    
    def extract_text(self, response: Any) -> str:
        if hasattr(response, 'choices') and response.choices:
            content = response.choices[0].message.content
            return content.strip() if content else ""
        return ""

    def create_initial_message(self, prompt: str) -> List:
        return [{"role": "user", "content": prompt}]

    def accumulate_messages(self, messages: List, response: Any, function_responses: List) -> None:
        # For OpenRouter, need to include assistant message with tool calls
        if hasattr(response, 'choices') and response.choices:
            assistant_msg = response.choices[0].message
            messages.append({
                "role": "assistant",
                "content": assistant_msg.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                    }
                    for tc in (assistant_msg.tool_calls or [])
                ]
            })
        messages.extend(function_responses)


class InferenceManager:
    """Manager class to handle provider initialization and operations"""
    
    @staticmethod
    def get_provider_config(provider_name: str) -> Dict[str, Any]:
        """Read provider config from providers.json"""
        config_path = Path(__file__).parent.parent / "providers.json"
        
        with open(config_path, 'r') as f:
            config = json.load(f)
        
        provider_config = config["model_providers"][provider_name].copy()
        
        # Override with env var
        env_key = f"{provider_name.upper()}_API_KEY"
        if os.getenv(env_key):
            provider_config["api_key"] = os.getenv(env_key)
        
        return provider_config
    
    @staticmethod
    def create_provider(provider_name: str) -> InferenceProvider:
        """Factory method to create provider instance"""
        if provider_name not in _PROVIDER_REGISTRY:
            raise ValueError(f"Unknown provider: {provider_name}. Available: {list(_PROVIDER_REGISTRY.keys())}")
        
        config = InferenceManager.get_provider_config(provider_name)
        provider_class = _PROVIDER_REGISTRY[provider_name]
        return provider_class(config)
    
    @staticmethod
    def get_tool_definitions() -> List[Dict[str, Any]]:
        """Get base tool definitions in JSON Schema format"""
        from .tool_definitions import get_tool_definitions
        return get_tool_definitions()
    
    @staticmethod
    def get_default_provider() -> str:
        """Get the default provider name from config"""
        config_path = Path(__file__).parent.parent / "providers.json"
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config.get("default_provider", "google")