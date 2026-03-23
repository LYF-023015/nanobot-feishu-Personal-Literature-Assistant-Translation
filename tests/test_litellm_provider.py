from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

import nanobot.providers.litellm_provider as litellm_provider_module
from nanobot.providers.litellm_provider import LiteLLMProvider


@dataclass
class _FakeMessage:
    content: str | None = None
    tool_calls: list[Any] | None = None


@dataclass
class _FakeChoice:
    message: _FakeMessage
    finish_reason: str = "stop"


@dataclass
class _FakeUsage:
    prompt_tokens: int = 1
    completion_tokens: int = 2
    total_tokens: int = 3


@dataclass
class _FakeResponse:
    choices: list[_FakeChoice]
    usage: _FakeUsage | None = None


class _FakeHttpResponse:
    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, Any]:
        return self._data


class _FakeHttpClient:
    def __init__(self, calls: list[dict[str, Any]]) -> None:
        self.calls = calls

    async def __aenter__(self) -> "_FakeHttpClient":
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None

    async def post(self, url: str, json: dict[str, Any], headers: dict[str, str]) -> _FakeHttpResponse:
        self.calls.append({"url": url, "json": json, "headers": headers})
        return _FakeHttpResponse(
            {
                "choices": [
                    {
                        "finish_reason": "",
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": "ok",
                            "tool_calls": [
                                {
                                    "id": "tool-1",
                                    "type": "function",
                                    "function": {
                                        "name": "demo",
                                        "arguments": "{}",
                                    },
                                }
                            ],
                        },
                    }
                ],
                "usage": {"prompt_tokens": 1, "completion_tokens": 2, "total_tokens": 3},
            }
        )


@pytest.mark.asyncio
async def test_chat_passes_reasoning_effort_when_provided(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    async def fake_acompletion(**kwargs: Any) -> _FakeResponse:
        calls.append(kwargs)
        return _FakeResponse(choices=[_FakeChoice(message=_FakeMessage(content="ok"))])

    monkeypatch.setattr(litellm_provider_module, "acompletion", fake_acompletion)

    provider = LiteLLMProvider(api_key="test-key", api_base="https://example.invalid/v1", default_model="openai/gpt-5.4")
    response = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
        tools=[{"type": "function", "function": {"name": "demo", "parameters": {"type": "object"}}}],
        model="openai/gpt-5.4",
        reasoning_effort="high",
    )

    assert response.content == "ok"
    assert len(calls) == 1
    assert calls[0]["reasoning_effort"] == "high"


@pytest.mark.asyncio
async def test_chat_does_not_pass_reasoning_effort_to_other_models(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    async def fake_acompletion(**kwargs: Any) -> _FakeResponse:
        calls.append(kwargs)
        return _FakeResponse(choices=[_FakeChoice(message=_FakeMessage(content="ok"))])

    monkeypatch.setattr(litellm_provider_module, "acompletion", fake_acompletion)

    provider = LiteLLMProvider(api_key="test-key", api_base="https://example.invalid/v1", default_model="openai/claude-opus-4-6-thinking")
    response = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
        tools=[{"type": "function", "function": {"name": "demo", "parameters": {"type": "object"}}}],
        model="openai/claude-opus-4-6-thinking",
        reasoning_effort="high",
    )

    assert response.content == "ok"
    assert len(calls) == 1
    assert "reasoning_effort" not in calls[0]


@pytest.mark.asyncio
async def test_chat_normalizes_temperature_for_gpt5_models(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    async def fake_acompletion(**kwargs: Any) -> _FakeResponse:
        calls.append(kwargs)
        return _FakeResponse(choices=[_FakeChoice(message=_FakeMessage(content="ok"))])

    monkeypatch.setattr(litellm_provider_module, "acompletion", fake_acompletion)

    provider = LiteLLMProvider(api_key="test-key", api_base="https://example.invalid/v1", default_model="openai/gpt-5.4")
    response = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
        tools=[{"type": "function", "function": {"name": "demo", "parameters": {"type": "object"}}}],
        model="openai/gpt-5.4",
    )

    assert response.content == "ok"
    assert len(calls) == 1
    assert calls[0]["temperature"] == 1.0


@pytest.mark.asyncio
async def test_chat_retries_without_tool_choice_when_backend_rejects_it(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    async def fake_acompletion(**kwargs: Any) -> _FakeResponse:
        calls.append(kwargs)
        if "tool_choice" in kwargs:
            raise RuntimeError("openai does not support parameters: ['tool_choice']")
        return _FakeResponse(choices=[_FakeChoice(message=_FakeMessage(content="ok"))])

    monkeypatch.setattr(litellm_provider_module, "acompletion", fake_acompletion)

    provider = LiteLLMProvider(api_key="test-key", api_base="https://example.invalid/v1", default_model="openai/claude-opus-4-6-thinking")
    response = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
        tools=[{"type": "function", "function": {"name": "demo", "parameters": {"type": "object"}}}],
        model="openai/claude-opus-4-6-thinking",
    )

    assert response.content == "ok"
    assert len(calls) == 2
    assert "tool_choice" in calls[0]
    assert "tool_choice" not in calls[1]


@pytest.mark.asyncio
async def test_chat_falls_back_to_raw_http_when_litellm_response_is_invalid(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []
    http_calls: list[dict[str, Any]] = []

    async def fake_acompletion(**kwargs: Any) -> _FakeResponse:
        calls.append(kwargs)
        raise RuntimeError("litellm.InternalServerError: InternalServerError: OpenAIException - Invalid response object")

    monkeypatch.setattr(litellm_provider_module, "acompletion", fake_acompletion)
    monkeypatch.setattr(litellm_provider_module.httpx, "AsyncClient", lambda **kwargs: _FakeHttpClient(http_calls))

    provider = LiteLLMProvider(api_key="test-key", api_base="https://example.invalid/v1", default_model="openai/claude-opus-4-6-thinking")
    response = await provider.chat(
        messages=[{"role": "user", "content": "hello"}],
        tools=[{"type": "function", "function": {"name": "demo", "parameters": {"type": "object"}}}],
        model="openai/claude-opus-4-6-thinking",
    )

    assert len(calls) == 1
    assert len(http_calls) == 1
    assert response.content == "ok"
    assert response.has_tool_calls
    assert response.finish_reason == "tool_calls"


def test_parse_openai_compatible_response_extracts_cache_tokens() -> None:
    provider = LiteLLMProvider(api_key="test-key", api_base="https://example.invalid/v1")
    response = provider._parse_openai_compatible_response(
        {
            "choices": [
                {
                    "message": {"content": "ok", "tool_calls": []},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 6,
                "total_tokens": 16,
                "cache_read_input_tokens": 4,
            },
        }
    )
    assert response.usage["prompt_tokens"] == 10
    assert response.usage["completion_tokens"] == 6
    assert response.usage["total_tokens"] == 16
    assert response.usage["cache_tokens"] == 4


def test_parse_openai_compatible_response_extracts_nested_cached_tokens() -> None:
    provider = LiteLLMProvider(api_key="test-key", api_base="https://example.invalid/v1")
    response = provider._parse_openai_compatible_response(
        {
            "choices": [
                {
                    "message": {"content": "ok", "tool_calls": []},
                    "finish_reason": "stop",
                }
            ],
            "usage": {
                "prompt_tokens": 20,
                "completion_tokens": 8,
                "total_tokens": 28,
                "prompt_tokens_details": {
                    "cached_tokens": 9,
                },
            },
        }
    )
    assert response.usage["cache_tokens"] == 9
