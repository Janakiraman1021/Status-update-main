"""Background scheduler. Runs the EOD automation tick every SCHEDULER_INTERVAL_SECONDS.

It can run inside the API process (SCHEDULER_ENABLED=true, the default for local use) or as a
dedicated worker:  python -m app.scheduler.jobs
Running more than one scheduler is safe: every side effect is guarded by atomic database claims.
"""
from __future__ import annotations

import atexit
import logging
import os
import signal
import threading

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask

from ..db import get_db
from ..services import EXTENSION_KEY, build_services

logger = logging.getLogger(__name__)
_JOB_ID = "worklog-eod-tick"


def run_tick(app: Flask) -> dict:
    with app.app_context():
        services = build_services(get_db(), app.config["SETTINGS"], app.extensions[EXTENSION_KEY])
        return services.scheduler.run_tick()


def start_scheduler(app: Flask) -> BackgroundScheduler | None:
    # Under the Werkzeug reloader only the child process should run jobs.
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return None
    if app.extensions.get("worklog_scheduler"):
        return app.extensions["worklog_scheduler"]
    settings = app.config["SETTINGS"]
    scheduler = BackgroundScheduler(timezone="UTC", job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 120})
    scheduler.add_job(lambda: run_tick(app), "interval", seconds=settings.SCHEDULER_INTERVAL_SECONDS, id=_JOB_ID, replace_existing=True)
    scheduler.start()
    app.extensions["worklog_scheduler"] = scheduler
    atexit.register(lambda: scheduler.shutdown(wait=False) if scheduler.running else None)
    logger.info("Scheduler started", extra={"event": "scheduler.started", "interval_seconds": settings.SCHEDULER_INTERVAL_SECONDS})
    return scheduler


def main() -> None:
    from .. import create_app

    app = create_app(start_scheduler=False)
    stop = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    interval = app.config["SETTINGS"].SCHEDULER_INTERVAL_SECONDS
    logger.info("Standalone scheduler running", extra={"interval_seconds": interval})
    while not stop.is_set():
        try:
            run_tick(app)
        except Exception:
            logger.exception("Scheduler tick failed")
        stop.wait(interval)


if __name__ == "__main__":
    main()
