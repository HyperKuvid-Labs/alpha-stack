import os
import json
import time
import requests
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from pathlib import Path
from dotenv import load_dotenv
from ..read_provider import get_providers

load_dotenv()


def retry_api_call(func, *args, max_retries: int = 10, **kwargs):
    attempt = 1
    while attempt <= max_retries:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries:
                raise  # Re-raise on final attempt
            wait_time = min(
                0.5 * (2 ** (attempt - 1)), 10
            )  # Exponential backoff, max 10s
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
        self.total_tokens_used = 0

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
    def create_function_response(
        self, function_name: str, result: Dict[str, Any], call_id: Optional[str] = None
    ) -> Any:
        """Create function response in provider format"""
        pass

    @abstractmethod
    def extract_text(self, response: Any) -> str:
        import re
        # it will not be json, so jsut removing this would be enough ``` ```
        match = re.search(r'```(?:[a-zA-Z0-9_\-+]+)?\s*\n([\s\S]*?)```', response, re.IGNORECASE)
        if match:
            return match.group(1).strip()
        return response.strip()

    @abstractmethod
    def create_initial_message(self, prompt: str) -> List:
        """Create initial message list with the given prompt in provider-specific format"""
        pass

    @abstractmethod
    def accumulate_messages(
        self, messages: List, response: Any, function_responses: List
    ) -> None:
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
                    parameters=self._convert_schema(tool_def["parameters"]),
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
            "object": types.Type.OBJECT,
        }

        for prop_name, prop_def in schema.get("properties", {}).items():
            prop_type = type_map.get(prop_def["type"].lower(), types.Type.STRING)
            properties[prop_name] = types.Schema(
                type=prop_type, description=prop_def.get("description", "")
            )

        return types.Schema(
            type=types.Type.OBJECT,
            properties=properties,
            required=schema.get("required", []),
        )

    def call_model(self, messages: List, tools: Any = None, **kwargs) -> Any:
        from google.genai import types

        contents = []
        for msg in messages:
            # If already a Content object (from agentic loop), use directly
            if isinstance(msg, types.Content):
                contents.append(msg)
            # If it's a GenerateContentResponse (model response), extract its content
            elif hasattr(msg, "candidates") and msg.candidates:
                # This is a response object - extract the content from first candidate
                if msg.candidates[0].content:
                    contents.append(msg.candidates[0].content)
            else:
                # Convert dict to Content
                contents.append(
                    types.Content(
                        role=msg.get("role", "user"),
                        parts=[types.Part.from_text(text=msg.get("content", ""))],
                    )
                )

        config_kwargs = {}
        if tools:
            config_kwargs["tools"] = [tools]
            config_kwargs["automatic_function_calling"] = (
                types.AutomaticFunctionCallingConfig(disable=True)
            )

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

        response = retry_api_call(self.get_client().models.generate_content, **call_kwargs)
        if hasattr(response, "usage_metadata") and hasattr(response.usage_metadata, "total_token_count"):
            self.total_tokens_used += response.usage_metadata.total_token_count
        return response

    def extract_function_calls(self, response: Any) -> List[Dict[str, Any]]:
        if not hasattr(response, "function_calls") or not response.function_calls:
            return []

        function_calls = []
        for fc in response.function_calls:
            args = (
                fc.args
                if isinstance(fc.args, dict)
                else (fc.args.__dict__ if hasattr(fc.args, "__dict__") else {})
            )
            function_calls.append({"name": fc.name, "args": args})
        return function_calls

    def create_function_response(
        self, function_name: str, result: Dict[str, Any], call_id: Optional[str] = None
    ) -> Any:
        from google.genai import types

        return types.Part.from_function_response(name=function_name, response=result)

    def extract_text(self, response: Any) -> str:
        return response.text.strip() if hasattr(response, "text") else ""

    def create_initial_message(self, prompt: str) -> List:
        from google.genai import types

        return [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]

    def accumulate_messages(
        self, messages: List, response: Any, function_responses: List
    ) -> None:
        from google.genai import types

        # Append the model's Content object (role='model', contains the function-call parts).
        # We extract it from the response instead of appending the raw GenerateContentResponse,
        # so the messages list stays as a uniform List[types.Content].
        if (
            hasattr(response, "candidates")
            and response.candidates
            and response.candidates[0].content
        ):
            messages.append(response.candidates[0].content)
        # Function results are returned as a 'user' turn — that is the format
        # Google's genai API expects for multi-turn tool-call conversations.
        messages.append(types.Content(role="user", parts=function_responses))


class OpenAICompatibleProvider(InferenceProvider):
    """Base class for all OpenAI-compatible providers (OpenAI, OpenRouter, vLLM, Prime Intellect, etc.)"""

    @abstractmethod
    def get_client(self):
        pass

    def format_tools(self, tool_definitions: List[Dict]) -> List[Dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": tool_def["name"],
                    "description": tool_def["description"],
                    "parameters": tool_def["parameters"],
                },
            }
            for tool_def in tool_definitions
        ]

    def call_model(
        self, messages: List[Dict], tools: List[Dict] = None, **kwargs
    ) -> Any:
        call_kwargs = {
            "model": self.model,
            "messages": messages,
        }
        if tools:
            call_kwargs["tools"] = tools
        for param in ["temperature", "max_tokens", "top_p"]:
            if param in kwargs:
                call_kwargs[param] = kwargs[param]
        response = retry_api_call(self.get_client().chat.completions.create, **call_kwargs)
        if hasattr(response, "usage") and hasattr(response.usage, "total_tokens"):
            self.total_tokens_used += response.usage.total_tokens
        return response

    def extract_function_calls(self, response: Any) -> List[Dict[str, Any]]:
        function_calls = []
        if hasattr(response, "choices") and response.choices:
            message = response.choices[0].message
            if hasattr(message, "tool_calls") and message.tool_calls:
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
                        function_calls.append(
                            {
                                "name": tool_call.function.name,
                                "args": args,
                                "id": tool_call.id,
                            }
                        )
        return function_calls

    def create_function_response(
        self, function_name: str, result: Dict[str, Any], call_id: Optional[str] = None
    ) -> Any:
        return {
            "role": "tool",
            "tool_call_id": call_id,
            "content": json.dumps(result) if not isinstance(result, str) else result,
        }

    def extract_text(self, response: Any) -> str:
        if hasattr(response, "choices") and response.choices:
            content = response.choices[0].message.content
            return content.strip() if content else ""
        return ""

    def create_initial_message(self, prompt: str) -> List:
        return [{"role": "user", "content": prompt}]

    def accumulate_messages(
        self, messages: List, response: Any, function_responses: List
    ) -> None:
        if hasattr(response, "choices") and response.choices:
            assistant_msg = response.choices[0].message
            messages.append(
                {
                    "role": "assistant",
                    "content": assistant_msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in (assistant_msg.tool_calls or [])
                    ],
                }
            )
        messages.extend(function_responses)


@register_provider("openai")
class OpenAIProvider(OpenAICompatibleProvider):
    def get_client(self):
        if self._client is None:
            from openai import OpenAI

            api_key = self.api_key or os.getenv("OPENAI_API_KEY")
            self._client = OpenAI(api_key=api_key)
        return self._client


@register_provider("openrouter")
class OpenRouterProvider(OpenAICompatibleProvider):
    def get_client(self):
        if self._client is None:
            from openai import OpenAI

            api_key = self.api_key or os.getenv("OPENROUTER_API_KEY")
            base_url = self.config.get("base_url", "https://openrouter.ai/api/v1")
            default_headers = {
                "HTTP-Referer": "https://pradheep.dev",
                "X-Title": "Alphastack",
            }
            self._client = OpenAI(
                api_key=api_key, base_url=base_url, default_headers=default_headers
            )
        return self._client


@register_provider("prime_intellect")
class PrimeIntellectProvider(OpenAICompatibleProvider):
    def get_client(self):
        if self._client is None:
            from openai import OpenAI

            api_key = self.api_key or os.getenv("PRIME_API_KEY")
            base_url = self.config.get("base_url", "https://api.pinference.ai/api/v1")
            self._client = OpenAI(api_key=api_key, base_url=base_url)
        return self._client


@register_provider("vllm")
class VLLMProvider(OpenAICompatibleProvider):
    def get_client(self):
        if self._client is None:
            from openai import OpenAI

            api_key = self.api_key or os.getenv("VLLM_API_KEY") or "dummy"
            base_url = self.config.get("base_url", "http://0.0.0.0:8000/v1")
            self._client = OpenAI(api_key=api_key, base_url=base_url)
        return self._client

    def _get_chat_completions_url(self) -> str:
        explicit_url = self.config.get("chat_completions_url")
        if explicit_url:
            return explicit_url

        base_url = str(self.config.get("base_url", "http://0.0.0.0:8000")).rstrip("/")
        if base_url.endswith("/v1"):
            return f"{base_url}/chat/completions"
        return f"{base_url}/v1/chat/completions"

    def _get_models_url(self) -> str:
        base_url = str(self.config.get("base_url", "http://0.0.0.0:8000")).rstrip("/")
        if base_url.endswith("/v1"):
            return f"{base_url}/models"
        return f"{base_url}/v1/models"

    def _resolve_model_name(self) -> str:
        model = self.model
        if model:
            return model

        models_url = self._get_models_url()
        response = retry_api_call(
            requests.get,
            models_url,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json() or {}
        model_data = data.get("data") or []
        if not model_data:
            raise ValueError(
                "vLLM returned no models and no model is configured. "
                "Set model under providers.json:model_providers.vllm.model or ensure /v1/models works."
            )
        first_model = model_data[0]
        model_id = first_model.get("id") if isinstance(first_model, dict) else ""
        if not model_id:
            raise ValueError(
                "vLLM returned model metadata without a valid id. "
                "Set model under providers.json:model_providers.vllm.model explicitly."
            )
        return model_id

    def call_model(self, messages: List[Dict], tools: List[Dict] = None, **kwargs) -> Any:
        # model = self._resolve_model_name()

        payload = {
            "model": "Qwen/Qwen3.5-2B",  # hardcoded for now since vLLM doesn't support dynamic model selection well
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        for param in ["temperature", "max_tokens", "top_p"]:
            if param in kwargs:
                payload[param] = kwargs[param]
        if "max_output_tokens" in kwargs and "max_tokens" not in payload:
            payload["max_tokens"] = kwargs["max_output_tokens"]

        # headers = {"Content-Type": "application/json"}
        # api_key = self.api_key or os.getenv("VLLM_API_KEY")
        # if api_key:
        #     headers["Authorization"] = f"Bearer {api_key}"

        response = retry_api_call(
            requests.post,
            self._get_chat_completions_url(),
            json=payload,
            # headers=headers, why the fuck we need header over here, mc
            # timeout=30,
        )
        response.raise_for_status()
        response_json = response.json()

        usage = response_json.get("usage") if isinstance(response_json, dict) else None
        if isinstance(usage, dict):
            total_tokens = usage.get("total_tokens")
            if isinstance(total_tokens, int):
                self.total_tokens_used += total_tokens

        return response_json

    def extract_function_calls(self, response: Any) -> List[Dict[str, Any]]:
        if isinstance(response, dict):
            function_calls = []
            choices = response.get("choices") or []
            if not choices:
                return function_calls

            message = choices[0].get("message") or {}
            tool_calls = message.get("tool_calls") or []
            for tool_call in tool_calls:
                if tool_call.get("type") != "function":
                    continue
                function = tool_call.get("function") or {}
                args = function.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError:
                        args = {}
                if not isinstance(args, dict):
                    args = {}
                function_calls.append(
                    {
                        "name": function.get("name", ""),
                        "args": args,
                        "id": tool_call.get("id"),
                    }
                )
            return function_calls
        return super().extract_function_calls(response)

    def extract_text(self, response: Any) -> str:
        if isinstance(response, dict):
            choices = response.get("choices") or []
            if not choices:
                return ""

            message = choices[0].get("message") or {}
            content = message.get("content")
            if isinstance(content, list):
                parts = []
                for part in content:
                    if isinstance(part, dict):
                        parts.append(part.get("text", ""))
                    else:
                        parts.append(str(part))
                content = "\n".join(parts)

            generated_text = (
                content
                or message.get("reasoning")
                or message.get("reasoning_content")
                or choices[0].get("text")
                or ""
            )
            return generated_text.strip()
        return super().extract_text(response)

    def accumulate_messages(
        self, messages: List, response: Any, function_responses: List
    ) -> None:
        if isinstance(response, dict):
            choices = response.get("choices") or []
            if choices:
                assistant_msg = choices[0].get("message") or {}
                messages.append(
                    {
                        "role": "assistant",
                        "content": assistant_msg.get("content") or "",
                        "tool_calls": assistant_msg.get("tool_calls") or [],
                    }
                )
            messages.extend(function_responses)
            return
        super().accumulate_messages(messages, response, function_responses)


class InferenceManager:
    """Manager class to handle provider initialization and operations"""

    _active_provider: Optional[InferenceProvider] = None
    _active_provider_name: Optional[str] = None

    @staticmethod
    def initialize(
        provider_name: Optional[str] = None, validate: bool = True
    ) -> InferenceProvider:
        """
        Initialize and cache a provider instance for the entire project run.
        Call this once at project startup.

        Args:
            provider_name: Provider to use (defaults to default_provider from config)
            validate: If True, validates API key exists

        Returns:
            The initialized provider instance
        """
        provider_name = provider_name or InferenceManager.get_default_provider()

        if (
            InferenceManager._active_provider is not None
            and InferenceManager._active_provider_name == provider_name
        ):
            return InferenceManager._active_provider

        config = InferenceManager.get_provider_config(provider_name)

        if validate:
            api_key = config.get("api_key") or os.getenv(
                f"{provider_name.upper()}_API_KEY"
            )
            if not api_key:
                raise ValueError(
                    f"API key not found for provider '{provider_name}'. "
                    f"Set {provider_name.upper()}_API_KEY env var or run 'alphastack setup'"
                )

        InferenceManager._active_provider = InferenceManager.create_provider(
            provider_name
        )
        InferenceManager._active_provider_name = provider_name

        return InferenceManager._active_provider

    @staticmethod
    def get_active_provider() -> InferenceProvider:
        """Get the cached provider instance. Initializes with default if not yet initialized."""
        if InferenceManager._active_provider is None:
            return InferenceManager.initialize()
        return InferenceManager._active_provider

    @staticmethod
    def get_total_tokens() -> int:
        if InferenceManager._active_provider:
            return InferenceManager._active_provider.total_tokens_used
        return 0

    @staticmethod
    def reset_tokens():
        if InferenceManager._active_provider:
            InferenceManager._active_provider.total_tokens_used = 0

    @staticmethod
    def reset():
        """Reset the cached provider (useful for testing)"""
        InferenceManager._active_provider = None
        InferenceManager._active_provider_name = None

    @staticmethod
    def get_provider_config(provider_name: str) -> Dict[str, Any]:
        all_providers = get_providers()
        if not isinstance(all_providers, dict):
            raise ValueError("Invalid providers.json format: 'model_providers' must be an object")
        if provider_name not in all_providers:
            raise ValueError(
                f"Unknown provider in providers.json: {provider_name}. "
                f"Available: {list(all_providers.keys())}"
            )
        return all_providers[provider_name]

    @staticmethod
    def create_provider(provider_name: str) -> InferenceProvider:
        """Factory method to create provider instance"""
        if provider_name not in _PROVIDER_REGISTRY:
            raise ValueError(
                f"Unknown provider: {provider_name}. Available: {list(_PROVIDER_REGISTRY.keys())}"
            )

        config = InferenceManager.get_provider_config(provider_name)
        provider_class = _PROVIDER_REGISTRY[provider_name]
        return provider_class(config)

    @staticmethod
    def get_tool_definitions() -> List[Dict[str, Any]]:
        """Get base tool definitions in JSON Schema format"""
        from .tool_definitions import get_tool_definitions

        return get_tool_definitions()

    @staticmethod
    def get_planner_tool_definitions(problem_statement_language: str = "others") -> List[Dict[str, Any]]:
        from .tool_definitions import get_planner_tool_definitions

        return get_planner_tool_definitions(problem_statement_language=problem_statement_language)

    @staticmethod
    def get_executor_tool_definitions() -> List[Dict[str, Any]]:
        """Get tool definitions filtered for the executor (file read/write only)."""
        from .tool_definitions import get_executor_tool_definitions

        return get_executor_tool_definitions()

    @staticmethod
    def get_default_provider() -> str:
        """Get the default provider name from config"""
        config_path = Path(__file__).parent.parent / "providers.json"
        with open(config_path, "r") as f:
            config = json.load(f)
        return config.get("default_provider", "google")
