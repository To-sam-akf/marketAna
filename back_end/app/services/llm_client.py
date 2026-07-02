from dataclasses import dataclass

from back_end.app.core.config import Settings, get_settings
from back_end.app.core.exceptions import AppException, ErrorCode


@dataclass(frozen=True)
class LLMClient:
    settings: Settings

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.llm_api_key and self.settings.llm_base_url)

    async def infer(self, prompt: str) -> dict:
        raise AppException(
            code=ErrorCode.LLM_UNCONFIGURED,
            message="LLM inference is not implemented in pn01",
        )


def get_llm_client() -> LLMClient:
    return LLMClient(settings=get_settings())
