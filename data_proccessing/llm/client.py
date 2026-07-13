"""Injectable LLM client protocol and generic HTTP implementation."""

from __future__ import annotations

import json
import time
from typing import Protocol, Sequence

import httpx


Message = dict[str, str]


class LLMClient(Protocol):
    def complete(self, messages: Sequence[Message]) -> str: ...


class HttpLLMClient:
    def __init__(
        self,
        *,
        api_key: str,
        base_url: str,
        model: str,
        timeout_seconds: int = 60,
        provider: str = "openai",
        max_retries: int = 0,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.provider = provider.casefold()
        self.max_retries = max(0, int(max_retries))

    def complete(self, messages: Sequence[Message]) -> str:
        if self.provider == "wenhua":
            return self._complete_wenhua(messages)
        return self._complete_openai(messages)

    def _complete_openai(self, messages: Sequence[Message]) -> str:
        response = httpx.post(
            self.base_url,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            json={"model": self.model, "messages": list(messages), "temperature": 0},
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        try:
            return str(payload["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("LLM response does not contain choices[0].message.content") from exc

    def _complete_wenhua(self, messages: Sequence[Message]) -> str:
        last_error = ""
        for attempt in range(self.max_retries + 1):
            try:
                headers = {"Accept": "text/event-stream", "Content-Type": "application/json"}
                if self.api_key:
                    headers["Authorization"] = f"Bearer {self.api_key}"
                with httpx.stream(
                    "POST",
                    self.base_url,
                    headers=headers,
                    json={"content": self._messages_to_content(messages)},
                    timeout=self.timeout_seconds + 10,
                ) as response:
                    response.raise_for_status()
                    parts: list[str] = []
                    for line in response.iter_lines():
                        content, stopped = self._parse_wenhua_sse_line(line)
                        if content:
                            parts.append(content)
                        if stopped:
                            break
                    if parts:
                        return "".join(parts)
                    last_error = "empty SSE response"
            except (httpx.TimeoutException, httpx.RequestError, httpx.HTTPStatusError) as exc:
                last_error = str(exc)
            if attempt < self.max_retries:
                time.sleep(2**attempt)
        raise RuntimeError(f"Wenhua LLM request failed: {last_error}")

    @staticmethod
    def _messages_to_content(messages: Sequence[Message]) -> str:
        return "\n\n".join(
            f"{message.get('role', 'user')}:\n{str(message.get('content') or '').strip()}"
            for message in messages
            if str(message.get("content") or "").strip()
        )

    @staticmethod
    def _parse_wenhua_sse_line(line: str) -> tuple[str, bool]:
        text = line.strip()
        if not text:
            return "", False
        if text.startswith("data:"):
            text = text[5:].strip()
        if text == "[DONE]":
            return "", True
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            return "", False
        choices = payload.get("choices") or []
        if not choices:
            return "", False
        first = choices[0]
        content = (first.get("delta") or {}).get("content") or ""
        return str(content), first.get("finish_reason") == "stop"
