"""MongoDB connection management and index creation."""
from __future__ import annotations

import logging

from flask import Flask, current_app
from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.database import Database

logger = logging.getLogger(__name__)

_EXTENSION_KEY = "worklog_db"


def create_client(uri: str):
    """Return a Mongo client. `mongomock://` gives an in-memory database (tests / offline demo)."""
    if uri.startswith("mongomock://"):
        import mongomock  # dev dependency only

        return mongomock.MongoClient(tz_aware=True)
    return MongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=10000, appname="worklog")


def init_db(app: Flask, client=None) -> Database:
    settings = app.config["SETTINGS"]
    client = client or create_client(settings.MONGODB_URI)
    db = client[settings.MONGODB_DATABASE]
    app.extensions[_EXTENSION_KEY] = db
    ensure_indexes(db)
    return db


def get_db() -> Database:
    return current_app.extensions[_EXTENSION_KEY]


def ensure_indexes(db: Database) -> None:
    db.users.create_index([("email", ASCENDING)], unique=True, name="uniq_email")

    db.sessions.create_index([("token_hash", ASCENDING)], unique=True, name="uniq_token")
    db.sessions.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_expires")

    db.projects.create_index([("user_id", ASCENDING), ("status", ASCENDING), ("name", ASCENDING)], name="user_status_name")
    db.projects.create_index([("user_id", ASCENDING), ("name_lower", ASCENDING)], unique=True, name="uniq_user_project_name")

    db.work_logs.create_index([("user_id", ASCENDING), ("work_date", ASCENDING)], unique=True, name="uniq_user_date")
    db.project_statuses.create_index(
        [("user_id", ASCENDING), ("project_id", ASCENDING), ("work_date", ASCENDING)],
        unique=True,
        name="uniq_user_project_status_date",
    )

    db.work_items.create_index([("user_id", ASCENDING), ("work_date", ASCENDING), ("timestamp", ASCENDING)], name="user_date_ts")
    db.work_items.create_index([("user_id", ASCENDING), ("project_id", ASCENDING), ("work_date", DESCENDING)], name="user_project_date")
    db.work_items.create_index([("user_id", ASCENDING), ("updated_at", DESCENDING)], name="user_recent")

    db.blockers.create_index([("user_id", ASCENDING), ("status", ASCENDING), ("identified_date", DESCENDING)], name="user_status_date")
    db.dependencies.create_index([("user_id", ASCENDING), ("status", ASCENDING), ("created_date", DESCENDING)], name="user_status_date")

    db.eod_reports.create_index([("user_id", ASCENDING), ("work_date", ASCENDING)], unique=True, name="uniq_user_date")
    db.eod_reports.create_index([("status", ASCENDING), ("sending_started_at", ASCENDING)], name="status_sending")
    db.eod_versions.create_index([("eod_id", ASCENDING), ("version", ASCENDING)], unique=True, name="uniq_eod_version")
    db.eod_versions.create_index([("user_id", ASCENDING), ("work_date", ASCENDING)], name="user_date")

    db.email_logs.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)], name="user_created")

    db.settings.create_index([("user_id", ASCENDING)], unique=True, name="uniq_user")
    db.job_locks.create_index([("key", ASCENDING)], unique=True, name="uniq_key")
    db.job_locks.create_index([("expires_at", ASCENDING)], expireAfterSeconds=0, name="ttl_expires")
    logger.debug("MongoDB indexes ensured")
