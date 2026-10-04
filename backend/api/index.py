import sys
from pathlib import Path

# Add backend directory to sys.path so app and run can be imported reliably
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from run import app


class VercelPathMiddleware:
    """Ensure PATH_INFO correctly reflects the requested route when deployed on Vercel."""

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO", "")
        # If Vercel rewrote the path to /api/index or /api/index.py, resolve to original request path
        if path in ("/api/index", "/api/index.py"):
            matched = (
                environ.get("HTTP_X_MATCHED_PATH")
                or environ.get("RAW_URI")
                or environ.get("HTTP_X_NOW_ROUTE_MATCHES")
            )
            if matched and not matched.startswith("/api/index"):
                environ["PATH_INFO"] = matched.split("?")[0]
            else:
                environ["PATH_INFO"] = "/"
        return self.wsgi_app(environ, start_response)


app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
