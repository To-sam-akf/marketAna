from back_end.app.api.health import health_check
from back_end.app.core.config import Settings, get_settings
from back_end.app.core.database import check_database_connection
from back_end.app.core.status import ARTICLE_STATUS_VALUES, ArticleProcessingStatus


def test_health_check_response_shape(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    get_settings.cache_clear()

    body = health_check()

    assert body["code"] == 0
    assert body["message"] == "ok"
    assert body["data"]["status"] == "ok"
    assert body["data"]["database"] in {"ok", "unconfigured", "error"}


def test_article_status_values_are_stable() -> None:
    assert ARTICLE_STATUS_VALUES == (-1, 0, 1, 2, 3, 4, 5)
    assert ArticleProcessingStatus.FAILED == -1
    assert ArticleProcessingStatus.PENDING == 0
    assert ArticleProcessingStatus.STORED == 5


def test_settings_defaults_load() -> None:
    settings = Settings()

    assert settings.app_name == "MarketANA"
    assert settings.task_batch_size == 20
    assert settings.rule_confidence_threshold == 0.7
    assert settings.scheduler_poll_interval_seconds == 300


def test_database_health_is_unconfigured_without_url() -> None:
    assert check_database_connection(None) == "unconfigured"
