"""
pn07 LLM API 客户端

使用 httpx 调用 OpenAI 兼容 API (/v1/chat/completions)。
支持自动重试（指数退避）和健康检查。
"""

from __future__ import annotations

import logging
import time

logger = logging.getLogger(__name__)


class LLMAPIClient:
    """OpenAI 兼容 API 客户端。

    Usage:
        config = LLMConfig.from_settings()
        client = LLMAPIClient(config)
        if client.health_check():
            response = client.chat([{"role": "user", "content": "..."}])
    """

    def __init__(self, config) -> None:
        """
        Args:
            config: pn07.models.LLMConfig 实例
        """
        self._config = config
        self._api_key = config.api_key
        self._base_url = config.base_url.rstrip("/")
        self._model = config.model
        self._timeout = config.timeout_seconds
        self._max_retries = config.max_retries

    @property
    def is_configured(self) -> bool:
        return self._config.is_configured

    def chat(self, messages: list[dict], *, retries: int | None = None) -> str:
        """
        发送 chat completion 请求。

        Args:
            messages: [{"role":"system","content":"..."}, {"role":"user","content":"..."}]
            retries: 最大重试次数（None=使用配置默认值）

        Returns:
            LLM 返回的文本内容

        Raises:
            RuntimeError: 所有重试耗尽或 API 配置无效
            ValueError: 4xx 客户端错误（不重试）
        """
        import httpx

        if not self.is_configured:
            raise RuntimeError("LLM API 未配置（缺少 api_key 或 base_url）")

        max_retries = retries if retries is not None else self._max_retries
        last_error = ""

        for attempt in range(max_retries + 1):
            try:
                url = f"{self._base_url}/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                }
                payload = {
                    "model": self._model,
                    "messages": messages,
                    "temperature": self._config.temperature,
                    "max_tokens": self._config.max_tokens,
                }

                response = httpx.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=self._timeout + 10,  # 额外 10s 缓冲
                )

                if response.status_code == 200:
                    data = response.json()
                    return data["choices"][0]["message"]["content"]

                elif response.status_code in (429, 500, 502, 503, 504):
                    # 可重试错误
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    if attempt < max_retries:
                        wait = 2 ** attempt
                        logger.warning("LLM API 重试 %s/%s, 等待 %ss: %s", attempt + 1, max_retries, wait, last_error)
                        time.sleep(wait)
                        continue

                elif response.status_code in (401, 403):
                    raise ValueError(f"LLM API 认证失败: HTTP {response.status_code}")

                elif response.status_code == 400:
                    raise ValueError(f"LLM API 请求错误: {response.text[:300]}")

                else:
                    last_error = f"HTTP {response.status_code}: {response.text[:200]}"
                    if attempt < max_retries:
                        time.sleep(2 ** attempt)
                        continue

            except httpx.TimeoutException:
                last_error = f"请求超时 ({self._timeout}s)"
                if attempt < max_retries:
                    logger.warning("LLM API 超时重试 %s/%s", attempt + 1, max_retries)
                    continue
            except httpx.RequestError as exc:
                last_error = f"网络错误: {exc}"
                if attempt < max_retries:
                    time.sleep(2 ** attempt)
                    continue

        raise RuntimeError(f"LLM API 调用失败（已重试 {max_retries} 次）: {last_error}")

    def health_check(self) -> bool:
        """快速验证 API 配置是否可用（发空消息检查连通性）。"""
        if not self.is_configured:
            return False
        try:
            import httpx
            url = f"{self._base_url}/v1/models"
            headers = {"Authorization": f"Bearer {self._api_key}"}
            resp = httpx.get(url, headers=headers, timeout=10)
            return resp.status_code == 200
        except Exception:
            return False
