"""Service container. Singletons (AI provider, email provider, rate limiter) live on the Flask app;
services are cheap objects composed per request or per scheduler tick."""
from __future__ import annotations

from dataclasses import dataclass

from flask import current_app, g

from ..db import get_db
from ..repositories import Repositories
from .ai_service import AIProvider
from .auth_service import AuthService
from .dashboard_service import DashboardService
from .email_service import EmailProvider, EmailService
from .eod_renderer import EmailTheme
from .eod_service import EodService
from .history_service import HistoryService
from .project_service import ProjectService
from .scheduler_service import SchedulerService
from .settings_service import SettingsService
from .tracking_service import TrackingService
from .work_log_service import WorkLogService

EXTENSION_KEY = "worklog_runtime"


@dataclass
class Runtime:
    ai: AIProvider
    email_provider: EmailProvider
    limiter: object


@dataclass
class Services:
    repos: Repositories
    auth: AuthService
    settings: SettingsService
    projects: ProjectService
    work_logs: WorkLogService
    tracking: TrackingService
    dashboard: DashboardService
    eod: EodService
    history: HistoryService
    scheduler: SchedulerService
    email: EmailService
    ai: AIProvider


def build_services(db, config, runtime: Runtime) -> Services:
    repos = Repositories.from_db(db)
    settings = SettingsService(repos, config)
    projects = ProjectService(repos)
    work_logs = WorkLogService(repos, projects, settings)
    email = EmailService(runtime.email_provider, repos.email_logs)
    eod = EodService(repos, runtime.ai, email, settings, work_logs, EmailTheme.from_settings(config))
    return Services(
        repos=repos,
        auth=AuthService(repos, config, runtime.limiter),
        settings=settings,
        projects=projects,
        work_logs=work_logs,
        tracking=TrackingService(repos, projects, settings),
        dashboard=DashboardService(repos, settings, work_logs),
        eod=eod,
        history=HistoryService(repos, settings, work_logs, runtime.ai),
        scheduler=SchedulerService(repos, settings, work_logs, eod, email, config),
        email=email,
        ai=runtime.ai,
    )


def get_services() -> Services:
    if "services" not in g:
        g.services = build_services(get_db(), current_app.config["SETTINGS"], current_app.extensions[EXTENSION_KEY])
    return g.services
