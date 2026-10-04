import sys
import urllib.parse
from pathlib import Path

# Add backend directory to sys.path so app and run can be imported reliably
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from run import app


class VercelPathMiddleware:
    """Ensure PATH_INFO reflects the actual requested path on Vercel."""

    def __init__(self, wsgi_app):
        self.wsgi_app = wsgi_app

    def __call__(self, environ, start_response):
        qs = environ.get("QUERY_STRING", "")
        if "__path__=" in qs:
            params = urllib.parse.parse_qs(qs)
            if "__path__" in params and params["__path__"]:
                raw_path = params["__path__"][0]
                clean_path = "/" + raw_path.lstrip("/")
                environ["PATH_INFO"] = clean_path
                params.pop("__path__", None)
                environ["QUERY_STRING"] = urllib.parse.urlencode(params, doseq=True)
        else:
            candidate = (
                environ.get("HTTP_X_FORWARDED_URI")
                or environ.get("HTTP_X_MATCHED_PATH")
                or environ.get("REQUEST_URI")
                or environ.get("RAW_URI")
            )
            if candidate:
                clean = candidate.split("?")[0]
                if clean and not clean.startswith("/api/index"):
                    environ["PATH_INFO"] = clean

        return self.wsgi_app(environ, start_response)


app.wsgi_app = VercelPathMiddleware(app.wsgi_app)
