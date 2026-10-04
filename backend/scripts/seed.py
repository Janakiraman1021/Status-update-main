"""Development seed data. Refuses to run when FLASK_ENV=production.

    python -m scripts.seed            # create demo user + sample data (idempotent)
    python -m scripts.seed --reset    # replace existing sample data

In single-user mode (APP_USER_EMAIL set) the data is added to that account; otherwise a demo user is created.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.db import get_db  # noqa: E402
from app.services import EXTENSION_KEY, build_services  # noqa: E402
from app.utils.datetime_utils import local_today  # noqa: E402

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "WorkLog@2026")
COLLECTIONS = ["projects", "work_logs", "work_items", "blockers", "dependencies", "eod_reports", "eod_versions",
               "email_logs", "settings", "sessions"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true", help="remove existing demo data first")
    args = parser.parse_args()

    app = create_app(start_scheduler=False)
    if app.config["SETTINGS"].is_production:
        sys.exit("Refusing to seed a production environment.")

    config = app.config["SETTINGS"]
    with app.app_context():
        db = get_db()
        services = build_services(db, config, app.extensions[EXTENSION_KEY])

        if config.single_user:
            # Single-user mode: sample data goes into the account defined by APP_USER_* (already ensured at startup).
            email, password = config.APP_USER_EMAIL, "(APP_USER_PASSWORD from backend/.env)"
            user = services.repos.users.by_email(email)
            if args.reset:
                for name in COLLECTIONS:
                    db[name].delete_many({"user_id": user["_id"]})
            elif services.repos.projects.count(user["_id"]):
                print(f"{email} already has data (use --reset to replace it with sample data)")
                return
        else:
            email, password = DEMO_EMAIL, DEMO_PASSWORD
            user = services.repos.users.by_email(email)
            if user and args.reset:
                for name in COLLECTIONS:
                    db[name].delete_many({"user_id": user["_id"]})
                db.users.delete_one({"_id": user["_id"]})
                user = None
            if user:
                print(f"Demo user already exists: {email} (use --reset to recreate)")
                return
            user = services.auth.create_user("Janakiraman", email, password)
        uid = user["_id"]
        projects = {name: services.projects.create(uid, name, desc) for name, desc in (
            ("Samunnati Statements Dashboard", "Account and repayment statements for internal teams"),
            ("Mail Classification System", "Automated triage of the shared inbox"),
            ("Internal Automation", "Scripts and workflows that remove manual effort"),
            ("Personal Development", "Learning and certifications"),
        )}
        dashboard = projects["Samunnati Statements Dashboard"]["_id"]
        services.settings.update(user, {"default_project_id": str(dashboard), "eod_time": "18:30", "timezone": "Asia/Kolkata"})

        today = date.fromisoformat(local_today("Asia/Kolkata"))
        yesterday = (today - timedelta(days=1)).isoformat()
        services.work_logs.upsert(uid, yesterday, {
            "project_id": str(dashboard),
            "quick_notes": "Reviewed statement filter requirements with the business team.",
            "next_steps": "Remove the statement selector from the Account and Repayment forms.",
        })
        for time, text, category, status in (
            ("10:00", "Removed the statement selector from the Account and Repayment forms.", "Enhancement", "Completed"),
            ("12:30", "Implemented light and dark mode.", "Development", "Completed"),
            ("15:00", "Added date validation.", "Enhancement", "Completed"),
            ("16:30", "Created access governance schema.", "Development", "Completed"),
            ("17:45", "94 automated tests passed.", "Testing", "Completed"),
        ):
            services.work_logs.create_item(uid, {"work_date": yesterday, "description": text, "category": category,
                                                 "status": status, "time": time, "project_id": str(dashboard)})
        services.tracking.create_blocker(uid, {
            "description": "Need confirmation on which date column should drive the Account Statement filter.",
            "identified_date": yesterday, "project_id": str(dashboard), "dependency": "Business team",
        })
        services.tracking.create_dependency(uid, {
            "description": "Need stakeholder approval for access governance table design.",
            "type": "Approval", "owner": "Data Governance", "created_date": yesterday, "project_id": str(dashboard),
        })
        services.eod.generate(user, yesterday)

        print("Seeded demo data.")
        print(f"  Email:    {email}")
        print(f"  Password: {password}")


if __name__ == "__main__":
    main()
