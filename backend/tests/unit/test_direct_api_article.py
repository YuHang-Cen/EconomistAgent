from __future__ import annotations

import logging
from typing import Any

import pytest
from app.services import direct_api_article


class _FakeResponse:
    def __init__(self, content: Any) -> None:
        self.content = content


class _FakeLlm:
    def __init__(self, *, content: Any = "", exc: Exception | None = None) -> None:
        self._content = content
        self._exc = exc

        self.invoke_kwargs: list[dict[str, Any]] = []

    def invoke(self, _prompt: str, **kwargs: Any) -> _FakeResponse:
        self.invoke_kwargs.append(kwargs)
        if self._exc is not None:
            raise self._exc
        return _FakeResponse(self._content)


class _SequenceLlm:
    def __init__(self, contents: list[str]) -> None:
        self.contents = contents
        self.prompts: list[str] = []
        self.invoke_kwargs: list[dict[str, Any]] = []

    def invoke(self, prompt: str, **kwargs: Any) -> _FakeResponse:
        self.prompts.append(prompt)
        self.invoke_kwargs.append(kwargs)
        return _FakeResponse(self.contents[len(self.prompts) - 1])


class _RateLimitError(RuntimeError):
    status_code = 429
    request_id = "request-123"


def _run(
    monkeypatch: pytest.MonkeyPatch,
    llm: _FakeLlm | _SequenceLlm | None,
) -> dict[str, Any]:
    monkeypatch.setattr(direct_api_article, "build_optional_llm", lambda: llm)
    monkeypatch.setattr(
        direct_api_article,
        "get_effective_model_config",
        lambda: {
            "provider": "test",
            "model_name": "test-model",
            "api_base": "https://example.invalid",
            "api_key": "must-not-be-logged",
        },
    )
    return direct_api_article.run_direct_api_article(
        "private user question",
        language="english",
        author_name="Test Economist",
    )


def test_returns_generated_status_for_valid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = _FakeLlm(content='{"title":"Generated","markdown":"A complete article."}')
    result = _run(
        monkeypatch,
        llm,
    )

    assert result == {
        "title": "Generated",
        "markdown": "A complete article.",
        "status": "generated",
        "error_code": None,
    }
    assert llm.invoke_kwargs == [{"response_format": direct_api_article.JSON_RESPONSE_FORMAT}]


def test_retries_once_after_invalid_json(monkeypatch: pytest.MonkeyPatch) -> None:
    llm = _SequenceLlm(
        [
            "not-json",
            '{"title":"Recovered","markdown":"A recovered article."}',
        ]
    )

    result = _run(monkeypatch, llm)

    assert result["status"] == "generated"
    assert result["title"] == "Recovered"
    assert len(llm.prompts) == 2
    assert "Output Correction" in llm.prompts[1]
    assert llm.invoke_kwargs == [
        {"response_format": direct_api_article.JSON_RESPONSE_FORMAT},
        {"response_format": direct_api_article.JSON_RESPONSE_FORMAT},
    ]


def test_logs_invoke_failure_without_sensitive_values(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=direct_api_article.__name__)

    result = _run(
        monkeypatch,
        _FakeLlm(exc=_RateLimitError("response body must remain private")),
    )

    assert result["status"] == "fallback"
    assert result["error_code"] == "llm_invoke_failed"
    assert "error_code=llm_invoke_failed" in caplog.text
    assert "exception_type=_RateLimitError" in caplog.text
    assert "status_code=429" in caplog.text
    assert "request_id=request-123" in caplog.text
    assert "private user question" not in caplog.text
    assert "response body must remain private" not in caplog.text
    assert "must-not-be-logged" not in caplog.text


def test_logs_invalid_json_by_length_and_hash_only(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    raw_response = "private malformed model response"
    caplog.set_level(logging.WARNING, logger=direct_api_article.__name__)

    result = _run(monkeypatch, _FakeLlm(content=raw_response))

    assert result["status"] == "fallback"
    assert result["error_code"] == "invalid_model_json"
    assert f"response_length={len(raw_response)}" in caplog.text
    assert "response_hash=" in caplog.text
    assert raw_response not in caplog.text


def test_distinguishes_missing_markdown_from_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=direct_api_article.__name__)

    result = _run(monkeypatch, _FakeLlm(content='{"title":"No body"}'))

    assert result["status"] == "fallback"
    assert result["error_code"] == "missing_markdown"
    assert "error_code=missing_markdown" in caplog.text


def test_marks_missing_llm_as_fallback(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=direct_api_article.__name__)

    result = _run(monkeypatch, None)

    assert result["status"] == "fallback"
    assert result["error_code"] == "llm_unavailable"
    assert "error_code=llm_unavailable" in caplog.text


def test_marks_llm_initialization_failure_as_fallback(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING, logger=direct_api_article.__name__)
    monkeypatch.setattr(
        direct_api_article,
        "get_effective_model_config",
        lambda: {
            "provider": "test",
            "model_name": "test-model",
            "api_base": "https://example.invalid",
            "api_key": "must-not-be-logged",
        },
    )

    def _raise_initialization_error() -> None:
        raise RuntimeError("private initialization detail")

    monkeypatch.setattr(
        direct_api_article,
        "build_optional_llm",
        _raise_initialization_error,
    )

    result = direct_api_article.run_direct_api_article("private user question")

    assert result["status"] == "fallback"
    assert result["error_code"] == "llm_initialization_failed"
    assert "error_code=llm_initialization_failed" in caplog.text
    assert "private initialization detail" not in caplog.text
