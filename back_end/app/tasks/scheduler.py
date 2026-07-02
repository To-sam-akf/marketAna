from apscheduler.schedulers.background import BackgroundScheduler

from back_end.app.core.config import Settings, get_settings


def create_scheduler(settings: Settings | None = None) -> BackgroundScheduler:
    resolved_settings = settings or get_settings()
    scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
    scheduler.configure(
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
        }
    )
    scheduler.add_job(
        lambda: None,
        trigger="interval",
        seconds=resolved_settings.scheduler_poll_interval_seconds,
        id="article_pipeline_placeholder",
        replace_existing=True,
    )
    return scheduler
