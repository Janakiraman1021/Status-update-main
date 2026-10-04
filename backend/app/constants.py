"""Domain enumerations shared across services."""

WORK_CATEGORIES = [
    "Development", "Enhancement", "Bug Fix", "Investigation", "Research", "Testing",
    "Deployment", "Documentation", "Meeting", "Support", "Learning", "Planning",
]
WORK_STATUSES = ["Planned", "In Progress", "Completed", "Blocked", "Deferred"]
PROJECT_STATUSES = ["Active", "Archived"]
BLOCKER_STATUSES = ["Open", "In Progress", "Resolved"]
DEPENDENCY_TYPES = ["Approval", "Information", "Dependency", "Decision", "Access"]
DEPENDENCY_STATUSES = ["Open", "In Progress", "Resolved"]
THEMES = ["light", "dark", "system"]
EOD_LENGTHS = ["short", "standard", "long", "detailed"]
EOD_TONES = ["professional", "executive", "corporate"]
# Legacy "generation style" values stored by earlier versions, mapped onto lengths.
LEGACY_STYLE_TO_LENGTH = {"concise": "short", "standard": "standard", "detailed": "detailed"}


class EodStatus:
    NOT_GENERATED = "NOT_GENERATED"
    GENERATING = "GENERATING"
    GENERATED = "GENERATED"
    SENDING = "SENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class EodFailure:
    GENERATION = "EOD_GENERATION_FAILED"
    EMAIL = "EMAIL_FAILED"
    DELIVERY_UNKNOWN = "EMAIL_DELIVERY_UNKNOWN"
