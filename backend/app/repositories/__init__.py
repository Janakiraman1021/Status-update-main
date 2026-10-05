from __future__ import annotations

from dataclasses import dataclass

from pymongo.database import Database

from .email_repository import EmailLogRepository
from .eod_repository import EodRepository, EodVersionRepository
from .project_repository import ProjectRepository
from .project_status_repository import ProjectStatusRepository
from .settings_repository import JobLockRepository, SettingsRepository
from .tracking_repository import BlockerRepository, DependencyRepository
from .user_repository import SessionRepository, UserRepository
from .work_log_repository import WorkItemRepository, WorkLogRepository


@dataclass
class Repositories:
    users: UserRepository
    sessions: SessionRepository
    projects: ProjectRepository
    project_statuses: ProjectStatusRepository
    work_logs: WorkLogRepository
    work_items: WorkItemRepository
    blockers: BlockerRepository
    dependencies: DependencyRepository
    eods: EodRepository
    eod_versions: EodVersionRepository
    email_logs: EmailLogRepository
    settings: SettingsRepository
    locks: JobLockRepository

    @classmethod
    def from_db(cls, db: Database) -> "Repositories":
        return cls(
            users=UserRepository(db),
            sessions=SessionRepository(db),
            projects=ProjectRepository(db),
            project_statuses=ProjectStatusRepository(db),
            work_logs=WorkLogRepository(db),
            work_items=WorkItemRepository(db),
            blockers=BlockerRepository(db),
            dependencies=DependencyRepository(db),
            eods=EodRepository(db),
            eod_versions=EodVersionRepository(db),
            email_logs=EmailLogRepository(db),
            settings=SettingsRepository(db),
            locks=JobLockRepository(db),
        )
