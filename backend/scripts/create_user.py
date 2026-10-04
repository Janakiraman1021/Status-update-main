"""Create a WorkLog user or reset a password (there is no public sign-up).

    python -m scripts.create_user --name "Your Name" --email you@company.com
    python -m scripts.create_user --email you@company.com --reset-password
The password is read interactively and never echoed or logged.
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.db import get_db  # noqa: E402
from app.services import EXTENSION_KEY, build_services  # noqa: E402
from app.utils.errors import AppError  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--name")
    parser.add_argument("--reset-password", action="store_true")
    args = parser.parse_args()

    password = getpass.getpass("Password: ")
    if password != getpass.getpass("Confirm password: "):
        sys.exit("Passwords do not match.")

    app = create_app(start_scheduler=False)
    with app.app_context():
        services = build_services(get_db(), app.config["SETTINGS"], app.extensions[EXTENSION_KEY])
        try:
            if args.reset_password:
                user = services.repos.users.by_email(args.email)
                if not user:
                    sys.exit("No user with that email.")
                services.auth.set_password(user["_id"], password)
                print("Password updated.")
            else:
                if not args.name:
                    sys.exit("--name is required when creating a user.")
                services.auth.create_user(args.name, args.email, password)
                print(f"User created: {args.email.lower()}")
        except AppError as exc:
            sys.exit(exc.message)


if __name__ == "__main__":
    main()
