from flask import Flask

from . import (
    auth, blockers, calendar, dashboard, dependencies, email, eod, health, history, projects, settings, work_items, work_logs,
)

BLUEPRINTS = [auth, dashboard, calendar, work_logs, work_items, projects, blockers, dependencies, eod, history, settings, email, health]


def register_routes(app: Flask) -> None:
    for module in BLUEPRINTS:
        app.register_blueprint(module.bp)
