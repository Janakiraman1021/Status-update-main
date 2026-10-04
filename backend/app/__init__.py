"""WorkLog Flask application factory."""
from __future__ import annotations

import logging

from flask import Flask
from flask_cors import CORS

from .config import Settings
from .db import init_db
from .middleware.error_handler import register_error_handlers
from .routes import register_routes
from .services import EXTENSION_KEY, Runtime
from .services.ai_service import AIProvider, create_ai_provider
from .services.email_service import EmailProvider, create_email_provider
from .utils.logging import configure_logging
from .utils.security import LoginRateLimiter

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None, *, mongo_client=None, ai_provider: AIProvider | None = None,
               email_provider: EmailProvider | None = None, start_scheduler: bool | None = None) -> Flask:
    settings = settings or Settings()
    settings.validate()
    configure_logging(settings.LOG_LEVEL)

    app = Flask(__name__, static_folder=None)
    app.config.update(
        SETTINGS=settings,
        SECRET_KEY=settings.SECRET_KEY,
        TESTING=settings.TESTING,
        MAX_CONTENT_LENGTH=1 * 1024 * 1024,
        JSON_SORT_KEYS=False,
    )
    CORS(app, origins=[settings.FRONTEND_URL], supports_credentials=True,
         allow_headers=["Content-Type", "X-CSRF-Token"], methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"])

    init_db(app, mongo_client)
    app.extensions[EXTENSION_KEY] = Runtime(
        ai=ai_provider or create_ai_provider(settings),
        email_provider=email_provider or create_email_provider(settings),
        limiter=LoginRateLimiter(settings.LOGIN_MAX_ATTEMPTS, settings.LOGIN_WINDOW_SECONDS),
    )
    register_error_handlers(app)
    register_routes(app)

    if settings.single_user:
        from .db import get_db
        from .services import build_services

        with app.app_context():
            build_services(get_db(), settings, app.extensions[EXTENSION_KEY]).auth.ensure_env_user()

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if response.mimetype == "application/json":
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    should_start = settings.SCHEDULER_ENABLED if start_scheduler is None else start_scheduler
    if should_start and not settings.TESTING:
        from .scheduler.jobs import start_scheduler as _start

        _start(app)

    runtime = app.extensions[EXTENSION_KEY]
    logger.info("WorkLog API ready", extra={"env": settings.FLASK_ENV, "ai_provider": runtime.ai.name,
                                            "email_provider": runtime.email_provider.name, "scheduler": bool(should_start)})
    return app
