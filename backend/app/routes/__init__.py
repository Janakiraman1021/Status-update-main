from flask import Flask

from . import (
    auth, blockers, calendar, dashboard, dependencies, email, eod, health, history, projects, project_statuses, root, settings, work_items, work_logs,
)

BLUEPRINTS = [root, auth, dashboard, calendar, work_logs, work_items, projects, project_statuses, blockers, dependencies, eod, history, settings, email, health]


def register_routes(app: Flask) -> None:
    for module in BLUEPRINTS:
        app.register_blueprint(module.bp)
