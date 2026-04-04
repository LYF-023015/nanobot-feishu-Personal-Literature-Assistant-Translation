"""LiteLLM provider implementation for multi-provider support."""

import json
import os
from typing import Any

import litellm
import httpx
from litellm import acompletion

from nanobot.providers.base import LLMProvider, LLMResponse, ToolCallRequest


class LiteLLMProvider(LLMProvider):
    """
    LLM provider using LiteLLM for multi-provider support.
    
    Supports OpenRouter, Anthropic, OpenAI, Gemini, and many other providers through
    a unified interface.
    """
    
    def __init__(
        self, 
        api_key: str | None = None, 
        api_base: str | None = None,
        default_model: str = "anthropic/claude-opus-4-5"
    ):
        super().__init__(api_key, api_base)
        self.default_model = default_model
        
        # Detect OpenRouter by api_key prefix or explicit api_base
        self.is_openrouter = (
            (api_key and api_key.startswith("sk-or-")) or
            (api_base and "openrouter" in api_base)
        )
        
        # Track if using vLLM endpoint (explicitly marked by model or api_base)
        self.is_vllm = (
            bool(api_base)
            and not self.is_openrouter
            and (
                "vllm" in default_model.lower() or
                (api_base and "vllm" in api_base.lower())
            )
        )
        
        # Configure LiteLLM based on provider
        if api_key:
            if self.is_openrouter:
                # OpenRouter mode - set key
                os.environ["OPENROUTER_API_KEY"] = api_key
            elif self.is_vllm:
                # vLLM/custom endpoint - uses OpenAI-compatible API
                os.environ["OPENAI_API_KEY"] = api_key
            elif "deepseek" in default_model:
                os.environ.setdefault("DEEPSEEK_API_KEY", api_key)
            elif "anthropic" in default_model:
                os.environ.setdefault("ANTHROPIC_API_KEY", api_key)
            elif "openai" in default_model or "gpt" in default_model:
                os.environ.setdefault("OPENAI_API_KEY", api_key)
            elif "gemini" in default_model.lower():
                os.environ.setdefault("GEMINI_API_KEY", api_key)
            elif "zhipu" in default_model or "glm" in default_model or "zai" in default_model:
                os.environ.setdefault("ZHIPUAI_API_KEY", api_key)
            elif "groq" in default_model:
                os.environ.setdefault("GROQ_API_KEY", api_key)
            elif "moonshot" in default_model or "kimi" in default_model:
                os.environ.setdefault("MOONSHOT_API_KEY", api_key)
                os.environ.setdefault("MOONSHOT_API_BASE", api_base or "https://api.moonshot.cn/v1")
            else:
                # Default to OpenAI-compatible API keys for custom endpoints
                os.environ.setdefault("OPENAI_API_KEY", api_key)
        
        if api_base:
            litellm.api_base = api_base
        
        # Disable LiteLLM logging noise
        litellm.suppress_debug_info = True
    
    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        reasoning_effort: str | None = None,
    ) -> LLMResponse:
        """
        Send a chat completion request via LiteLLM.
        
        Args:
            messages: List of message dicts with 'role' and 'content'.
            tools: Optional list of tool definitions in OpenAI format.
            model: Model identifier (e.g., 'anthropic/claude-sonnet-4-5').
            max_tokens: Maximum tokens in response.
            temperature: Sampling temperature.
            reasoning_effort: Optional reasoning mode hint for supported models.
        
        Returns:
            LLMResponse with content and/or tool calls.
        """
        model = model or self.default_model
        
        # For OpenRouter, prefix model name if not already prefixed
        if self.is_openrouter and not model.startswith("openrouter/"):
            model = f"openrouter/{model}"
        
        # For Zhipu/Z.ai, ensure prefix is present
        # Handle cases like "glm-4.7-flash" -> "zai/glm-4.7-flash"
        if ("glm" in model.lower() or "zhipu" in model.lower()) and not (
            model.startswith("zhipu/") or 
            model.startswith("zai/") or 
            model.startswith("openrouter/")
        ):
            model = f"zai/{model}"

        # For Moonshot/Kimi, ensure moonshot/ prefix (before vLLM check)
        if ("moonshot" in model.lower() or "kimi" in model.lower()) and not (
            model.startswith("moonshot/") or model.startswith("openrouter/")
        ):
            model = f"moonshot/{model}"

        # For Gemini, ensure gemini/ prefix if not already present
        if ("gemini" in model.lower() and not model.startswith("gemini/") and not model.startswith("openai/")):
            model = f"gemini/{model}"

        # For vLLM, use hosted_vllm/ prefix per LiteLLM docs
        # Convert openai/ prefix to hosted_vllm/ if user specified it
        if self.is_vllm:
            model = f"hosted_vllm/{model}"
        
        # kimi-k2.5 only supports temperature=1.0
        if "kimi-k2.5" in model.lower():
            temperature = 1.0

        # gpt-5 family models reject non-1.0 temperatures in LiteLLM/OpenAI-compatible
        # routes, so normalize them here instead of surfacing a provider error.
        if "gpt-5" in model.lower() and temperature != 1.0:
            temperature = 1.0

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        
        # Pass api_base directly for custom endpoints (vLLM, etc.)
        if self.api_base:
            kwargs["api_base"] = self.api_base
        
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        if reasoning_effort is not None and self._supports_reasoning_effort(model):
            kwargs["reasoning_effort"] = reasoning_effort
        
        try:
            response = await acompletion(**kwargs)
            return self._parse_response(response)
        except Exception as e:
            if tools and self._should_retry_without_tool_choice(e):
                retry_kwargs = dict(kwargs)
                retry_kwargs.pop("tool_choice", None)
                try:
                    response = await acompletion(**retry_kwargs)
                    return self._parse_response(response)
                except Exception as retry_error:
                    return LLMResponse(
                        content=f"Error calling LLM: {str(retry_error)}",
                        finish_reason="error",
                    )
            if self.api_base and self._should_fallback_to_raw_http(e):
                try:
                    return await self._chat_via_raw_openai_compatible_api(kwargs)
                except Exception as raw_error:
                    return LLMResponse(
                        content=f"Error calling LLM: {str(raw_error)}",
                        finish_reason="error",
                    )
            # Return error as content for graceful handling
            return LLMResponse(
                content=f"Error calling LLM: {str(e)}",
                finish_reason="error",
            )

    def _should_retry_without_tool_choice(self, error: Exception) -> bool:
        message = str(error).lower()
        return "tool_choice" in message and (
            "unsupported" in message or "does not support" in message
        )

    def _supports_reasoning_effort(self, model: str) -> bool:
        return "gpt-5" in model.lower()

    def _should_fallback_to_raw_http(self, error: Exception) -> bool:
        message = str(error).lower()
        return (
            self.api_base is not None
            and "invalid response object" in message
        )

    async def _chat_via_raw_openai_compatible_api(self, kwargs: dict[str, Any]) -> LLMResponse:
        payload = {
            "model": kwargs["model"],
            "messages": kwargs["messages"],
            "max_tokens": kwargs["max_tokens"],
            "temperature": kwargs["temperature"],
        }

        for key in ("tools", "tool_choice", "reasoning_effort"):
            if key in kwargs:
                payload[key] = kwargs[key]

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        base_url = self.api_base.rstrip("/") if self.api_base else ""
        url = f"{base_url}/chat/completions"

        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return self._parse_openai_compatible_response(response.json())

    def _parse_openai_compatible_response(self, data: dict[str, Any]) -> LLMResponse:
        choices = data.get("choices") or []
        if not choices:
            return LLMResponse(content="", finish_reason="error")

        choice = choices[0] or {}
        message = choice.get("message") or {}
        tool_calls = []

        for tc in message.get("tool_calls") or []:
            function = tc.get("function") or {}
            args = function.get("arguments")
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except json.JSONDecodeError as e:
                    args = {
                        "__nanobot_tool_args_error__": "json_decode_error",
                        "__nanobot_tool_args_error_msg__": str(e),
                        "__nanobot_tool_args_raw__": args[:2000],
                    }
            if not isinstance(args, dict):
                args = {
                    "__nanobot_tool_args_error__": "non_object_arguments",
                    "__nanobot_tool_args_error_msg__": f"arguments must be a JSON object, got {type(args).__name__}",
                    "__nanobot_tool_args_raw__": str(args)[:2000],
                }

            tool_calls.append(ToolCallRequest(
                id=tc.get("id", ""),
                name=function.get("name", ""),
                arguments=args,
            ))

        finish_reason = choice.get("finish_reason") or ("tool_calls" if tool_calls else "stop")

        usage = self._extract_usage(data.get("usage") or {})

        return LLMResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            finish_reason=finish_reason,
            usage=usage,
        )
    
    def _parse_response(self, response: Any) -> LLMResponse:
        """Parse LiteLLM response into our standard format."""
        choice = response.choices[0]
        message = choice.message
        
        tool_calls = []
        if hasattr(message, "tool_calls") and message.tool_calls:
            for tc in message.tool_calls:
                # Parse arguments from JSON string if needed
                args = tc.function.arguments
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except json.JSONDecodeError as e:
                        args = {
                            "__nanobot_tool_args_error__": "json_decode_error",
                            "__nanobot_tool_args_error_msg__": str(e),
                            "__nanobot_tool_args_raw__": args[:2000],
                        }
                if not isinstance(args, dict):
                    args = {
                        "__nanobot_tool_args_error__": "non_object_arguments",
                        "__nanobot_tool_args_error_msg__": f"arguments must be a JSON object, got {type(args).__name__}",
                        "__nanobot_tool_args_raw__": str(args)[:2000],
                    }
                
                tool_calls.append(ToolCallRequest(
                    id=tc.id,
                    name=tc.function.name,
                    arguments=args,
                ))
        
        usage = self._extract_usage(getattr(response, "usage", None))
        
        return LLMResponse(
            content=message.content,
            tool_calls=tool_calls,
            finish_reason=choice.finish_reason or "stop",
            usage=usage,
        )
    
    def get_default_model(self) -> str:
        """Get the default model."""
        return self.default_model

    @staticmethod
    def _to_int(value: Any) -> int:
        try:
            if value is None:
                return 0
            if isinstance(value, bool):
                return 0
            return max(0, int(value))
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _get_usage_attr(usage: Any, key: str, default: Any = 0) -> Any:
        if usage is None:
            return default
        if isinstance(usage, dict):
            return usage.get(key, default)
        return getattr(usage, key, default)

    def _extract_usage(self, usage: Any) -> dict[str, int]:
        if not usage:
            return {}

        prompt_tokens = self._to_int(self._get_usage_attr(usage, "prompt_tokens", 0))
        completion_tokens = self._to_int(self._get_usage_attr(usage, "completion_tokens", 0))
        total_tokens = self._to_int(self._get_usage_attr(usage, "total_tokens", 0))

        cache_tokens = 0
        prompt_details = self._get_usage_attr(usage, "prompt_tokens_details", {})
        cache_tokens = self._to_int(self._get_usage_attr(prompt_details, "cached_tokens", 0))

        if cache_tokens <= 0:
            for key in (
                "prompt_cache_hit_tokens",
                "cache_read_input_tokens",
                "cached_prompt_tokens",
                "input_cached_tokens",
            ):
                value = self._to_int(self._get_usage_attr(usage, key, 0))
                if value > 0:
                    cache_tokens = value
                    break

        # Some providers expose a generic `cache_tokens` field with ambiguous meaning.
        # Only use it as a fallback and clamp to prompt_tokens to avoid impossible splits.
        if cache_tokens <= 0:
            generic_cache = self._to_int(self._get_usage_attr(usage, "cache_tokens", 0))
            if 0 < generic_cache <= prompt_tokens:
                cache_tokens = generic_cache

        cache_tokens = min(cache_tokens, prompt_tokens)

        # Workaround: some proxy providers (e.g. yeysai.com) under-report prompt_tokens
        # while total_tokens remains accurate. If prompt_tokens is suspiciously small
        # (i.e. < total_tokens - completion_tokens), use the derived value instead.
        if total_tokens > 0 and completion_tokens >= 0:
            derived_prompt = total_tokens - completion_tokens
            if derived_prompt > prompt_tokens:
                prompt_tokens = derived_prompt
                # Re-clamp cache_tokens against the corrected prompt_tokens
                cache_tokens = min(cache_tokens, prompt_tokens)

        return {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
            "cache_tokens": cache_tokens,
        }
