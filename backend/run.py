"""Entry point.

Development:   python run.py
Production:    waitress-serve --listen=0.0.0.0:5000 --call app:create_app      (Windows)
               gunicorn -w 1 -b 0.0.0.0:5000 "app:create_app()"               (Linux)
"""
import os

from app import create_app
from app.config.settings import ENV_FILE

app = create_app()

if __name__ == "__main__":
    settings = app.config["SETTINGS"]
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5000")),
        debug=not settings.is_production,
        use_reloader=not settings.is_production,
        extra_files=[str(ENV_FILE)],  # restart automatically when backend/.env is edited
    )
