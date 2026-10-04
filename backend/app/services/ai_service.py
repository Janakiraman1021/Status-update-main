"""AI provider abstraction for EOD generation, work categorization and summarization.

Providers are selected with AI_PROVIDER:
  local      deterministic, offline formatter that only rearranges the user's own words (default)
  groq       open models on Groq, e.g. Qwen (AI_API_KEY, AI_MODEL; default qwen/qwen3.8-27b)
Add a provider by subclassing AIProvider and registering it in PROVIDERS.
"""
from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Any

from ..constants import WORK_CATEGORIES, WORK_STATUSES

logger = logging.getLogger(__name__)


class AIError(Exception):
    """Raised when the provider cannot produce a usable result."""


@dataclass
class EodDraft:
    executive_snapshot: str = ""
    key_deliverables: list[str] = field(default_factory=list)
    workstreams: list[dict] = field(default_factory=list)  # [{"title": str, "items": [str]}]
    quality_assurance: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    asks: list[str] = field(default_factory=list)
    next_steps: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "EodDraft":
        def strings(key: str) -> list[str]:
            return [s.strip() for s in data.get(key) or [] if isinstance(s, str) and s.strip()]

        workstreams = []
        for ws in data.get("workstreams") or []:
            if isinstance(ws, dict):
                items = [s.strip() for s in ws.get("items") or [] if isinstance(s, str) and s.strip()]
                title = str(ws.get("title") or "").strip()
                if items:
                    workstreams.append({"title": title, "items": items})
        return cls(
            executive_snapshot=str(data.get("executive_snapshot") or "").strip(),
            key_deliverables=strings("key_deliverables"),
            workstreams=workstreams,
            quality_assurance=strings("quality_assurance"),
            blockers=strings("blockers"),
            asks=strings("asks"),
            next_steps=strings("next_steps"),
        )

    def to_dict(self) -> dict:
        return asdict(self)

    def is_empty(self) -> bool:
        return not any([self.executive_snapshot, self.key_deliverables, self.workstreams, self.quality_assurance,
                        self.blockers, self.asks, self.next_steps])


EOD_SYSTEM_PROMPT = """You are a professional corporate status-report writer.

Transform the user's documented work into a clear, professional EOD status update.

Important rules:
1. Never invent information.
2. Never fabricate metrics.
3. Never invent achievements.
4. Never invent business impact.
5. Never invent meetings.
6. Never invent blockers.
7. Never invent names.
8. Never invent dates.
9. Preserve technical accuracy.
10. Improve grammar and structure.
11. Use professional corporate language.
12. Keep the report factual.
13. Omit sections for which no information exists (return an empty string or empty list).
14. Do not exaggerate the user's contribution.
15. Do not change the underlying meaning.

The input represents actual work performed by the user. Preserve the completion state the user recorded:
work the user "investigated", "looked into" or marked "In Progress" must not be described as resolved,
completed, fixed or stabilised. Only describe something as completed when the user recorded it as done.
Keep every number exactly as the user wrote it and do not add numbers that are not in the input.
Write plain sentences without markdown formatting.
Never use em dashes or en dashes (— or –). Use commas, colons, semicolons or separate sentences instead.
Do not start bullets with a dash; return each bullet as plain text.

Section guidance:
- executive_snapshot: 1-3 sentences summarising the main outcomes of the day.
- key_deliverables: completed work items.
- workstreams: related work grouped under a short title (use the project or functional area the user gave).
- quality_assurance: tests, validation and verification the user recorded.
- blockers: unresolved blockers and dependencies.
- asks: actions, approvals or decisions required from other people.
- next_steps: planned follow-up the user recorded."""

LENGTH_HINTS = {
    "short": ("Length: SHORT. A one-sentence executive snapshot, at most 5 crisp bullets per section, "
              "merge closely related items, and leave workstream details empty."),
    "standard": ("Length: STANDARD. A two-sentence executive snapshot, one concise bullet per item, "
                 "and workstream details only when work spans more than one area."),
    "long": ("Length: LONG. A three-sentence executive snapshot, a full bullet for every item with its context "
             "and purpose as recorded, and workstream details grouping the work by area."),
    "detailed": ("Length: DETAILED. A comprehensive report for senior stakeholders: a three to four sentence executive snapshot, "
                 "descriptive bullets that carry every recorded technical detail, scope, rationale and status, "
                 "and complete workstream details. Elaborate only with information present in the input."),
}

TONE_HINTS = {
    "professional": ("Tone: PROFESSIONAL. Clear, natural business English. Avoid clichés such as "
                     "\"move the needle\", \"boil the ocean\", \"north star\", \"synergy\" and \"low-hanging fruit\"."),
    "executive": ("Tone: EXECUTIVE. Write in polished, senior-level corporate language suitable for leadership: "
                  "precise action verbs (delivered, operationalised, streamlined, consolidated, remediated, institutionalised, "
                  "de-risked), outcome-oriented phrasing, governance and stakeholder vocabulary, and confident, formal sentences. "
                  "Sophistication applies to wording only: never add outcomes, impact, metrics or completion that the user did not record."),
    "corporate": ("Tone: CORPORATE. Write in full big-company corporate jargon with plenty of buzzwords. Use framing phrases "
                  "generously: \"circling back\", \"level-set\", \"move the needle\", \"north star\", \"double-click\", "
                  "\"take offline\", \"ping me\", \"boil the ocean\" (e.g. \"without trying to boil the ocean\"). "
                  "Use domain terms only where the recorded work genuinely involves that concept: \"T-1\" (previous-day data), "
                  "\"defense-in-depth\" and \"ring-fenced\" (security or isolation work), \"zero blast radius\" (changes with no impact "
                  "elsewhere), \"single pane of glass\" (consolidated views or dashboards), \"maker-checker\" (approval or review controls), "
                  "\"go-live\" (only if a release is recorded as planned or done). Jargon shapes the wording only: never claim a go-live, "
                  "control, outcome, metric or completion the user did not record."),
}


@dataclass(frozen=True)
class GenerationOptions:
    length: str = "standard"
    tone: str = "executive"

    @classmethod
    def from_any(cls, value: "GenerationOptions | dict | str | None") -> "GenerationOptions":
        if isinstance(value, GenerationOptions):
            return value
        if isinstance(value, str):  # legacy single "style" argument
            return cls(length={"concise": "short"}.get(value, value if value in LENGTH_HINTS else "standard"))
        value = value or {}
        length = value.get("length") if value.get("length") in LENGTH_HINTS else "standard"
        tone = value.get("tone") if value.get("tone") in TONE_HINTS else "executive"
        return cls(length=length, tone=tone)

    def prompt(self) -> str:
        return f"{LENGTH_HINTS[self.length]}\n{TONE_HINTS[self.tone]}"


_DASH_BETWEEN_DIGITS = re.compile(r"(?<=\d)\s*[–—]\s*(?=\d)")
_SPACED_DASH = re.compile(r"\s+[–—]\s+|\s*—\s*")
_LEADING_DASH = re.compile(r"^\s*[–—-]+\s*")


def remove_dashes(text: str) -> str:
    """Replace em/en dashes: ranges become hyphens (1–3 → 1-3), clause dashes become commas."""
    if not text:
        return text
    text = _DASH_BETWEEN_DIGITS.sub("-", text)
    text = _SPACED_DASH.sub(", ", text)
    text = text.replace("–", "-")
    text = re.sub(r",\s*,", ",", text)
    return re.sub(r",\s*([.;:])", r"\1", text).strip()


def clean_draft(draft: "EodDraft") -> "EodDraft":
    """Apply house style to any provider's output: no em/en dashes, no leading bullet dashes."""
    def fix(value: str) -> str:
        return remove_dashes(_LEADING_DASH.sub("", value))

    return EodDraft(
        executive_snapshot=fix(draft.executive_snapshot),
        key_deliverables=[fix(v) for v in draft.key_deliverables],
        workstreams=[{"title": fix(ws.get("title", "")), "items": [fix(i) for i in ws["items"]]} for ws in draft.workstreams],
        quality_assurance=[fix(v) for v in draft.quality_assurance],
        blockers=[fix(v) for v in draft.blockers],
        asks=[fix(v) for v in draft.asks],
        next_steps=[fix(v) for v in draft.next_steps],
    )

EOD_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "executive_snapshot": {"type": "string"},
        "key_deliverables": {"type": "array", "items": {"type": "string"}},
        "workstreams": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"title": {"type": "string"}, "items": {"type": "array", "items": {"type": "string"}}},
                "required": ["title", "items"],
                "additionalProperties": False,
            },
        },
        "quality_assurance": {"type": "array", "items": {"type": "string"}},
        "blockers": {"type": "array", "items": {"type": "string"}},
        "asks": {"type": "array", "items": {"type": "string"}},
        "next_steps": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["executive_snapshot", "key_deliverables", "workstreams", "quality_assurance", "blockers", "asks", "next_steps"],
    "additionalProperties": False,
}

CATEGORIZE_SYSTEM_PROMPT = f"""You split informal work notes into individual work entries and suggest a category and status for each.
Keep each description faithful to the note: fix grammar and capitalisation only, never add detail.
Categories: {", ".join(WORK_CATEGORIES)}. Statuses: {", ".join(WORK_STATUSES)}.
Use status "Completed" only if the note says the work was done (past tense such as "added", "fixed", "removed", "passed").
Use "In Progress" for ongoing work, "Blocked" for blocked work, "Planned" for future work. Use null when unclear.
Skip anything that is not a piece of work: subject lines, greetings, pleasantries, section headings and sign-offs."""

CATEGORIZE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "description": {"type": "string"},
                    "category": {"anyOf": [{"type": "string", "enum": WORK_CATEGORIES}, {"type": "null"}]},
                    "status": {"anyOf": [{"type": "string", "enum": WORK_STATUSES}, {"type": "null"}]},
                },
                "required": ["description", "category", "status"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["items"],
    "additionalProperties": False,
}

SUMMARY_SYSTEM_PROMPT = """You summarise a professional's documented work for a period into a short factual summary
(one paragraph followed by up to eight plain-text bullet lines starting with "- ").
Never invent information, metrics, outcomes or names. Preserve completion states exactly as recorded."""


class AIProvider(ABC):
    name = "base"

    def __init__(self, model: str = ""):
        self.model = model

    @abstractmethod
    def generate_eod(self, context: dict, options: "GenerationOptions | dict | str | None" = None) -> EodDraft: ...

    @abstractmethod
    def categorize(self, text: str) -> list[dict]: ...

    @abstractmethod
    def summarize(self, text: str) -> str: ...


# --------------------------------------------------------------------------
# Local deterministic provider
# --------------------------------------------------------------------------

_ASK_RE = re.compile(r"\b(need|needs|needed|awaiting|waiting (for|on)|pending (from|with)|require[sd]?|request(ed)? (approval|access)|approval)\b", re.I)
_BLOCK_RE = re.compile(r"\b(blocked|blocker|stuck|unable to|can't|cannot)\b", re.I)
# "validation" alone is usually a feature ("implemented date validation"), so only verbs/test terms count as QA.
_QA_RE = re.compile(r"\b(tests?|tested|testing|passed|validated|verified|qa|uat|regression)\b", re.I)
_NEXT_RE = re.compile(r"^(next|tomorrow|todo|to do|plan(ned)?|will)\b[:\s-]*", re.I)
_PROGRESS_RE = re.compile(r"\b(working on|in progress|wip|started|ongoing|continuing|investigat\w*|looking into|looked into)\b", re.I)
_BULLET_RE = re.compile(r"^\s*(?:[-*•]+|\d+[.)])\s*")
_WORKED_ON_RE = re.compile(r"^(worked on)\b", re.I)
_SHORT_LIMIT = 3
# Executive wording for the local writer: synonyms only, so the recorded meaning and completion state stay intact.
_EXECUTIVE_VERBS = [(re.compile(rf"^{src}\b", re.I), dst) for src, dst in (
    ("worked on", "Advanced work on"),
    ("added", "Introduced"),
    ("created", "Established"),
    ("removed", "Retired"),
    ("fixed", "Remediated"),
    ("improved", "Enhanced"),
    ("updated", "Refined"),
    ("built", "Engineered"),
    ("completed", "Delivered"),
    ("finished", "Delivered"),
    ("started", "Initiated"),
    ("set up", "Stood up"),
    ("need", "Pending:"),
    ("needs", "Pending:"),
)]
_SIGNOFF_RE = re.compile(r"^(thanks|thank you|regards|best regards|thanks and regards|warm regards|cheers)\b[\s,.!]*$", re.I)
# Email scaffolding that is not work: subject lines, greetings, pleasantries and sign-offs.
_NOT_WORK_RE = re.compile(
    r"^(subject\s*:|(hi|hello|hey|dear)\b[^.]{0,40}[,!]?$|trust you are doing well|hope you are (doing )?well|"
    r"(thanks|thank you|regards|best regards|thanks and regards|cheers)\b[\s,.!]*$)",
    re.I,
)


def is_not_work(line: str) -> bool:
    """True for greetings, sign-offs, subject lines and ALL-CAPS section headings."""
    text = line.strip()
    if _NOT_WORK_RE.match(text):
        return True
    letters = [c for c in text if c.isalpha()]
    return bool(letters) and text == text.upper() and len(text) <= 60 and len(text.split()) <= 6

_CATEGORY_KEYWORDS: list[tuple[str, re.Pattern]] = [
    ("Bug Fix", re.compile(r"\b(fix(ed|es)?|bug|defect|hotfix|issue)\b", re.I)),
    ("Testing", _QA_RE),
    ("Deployment", re.compile(r"\b(deploy(ed|ment)?|release[d]?|rollout|ci/cd|pipeline)\b", re.I)),
    ("Documentation", re.compile(r"\b(document(ed|ation)?|docs?|readme|wiki)\b", re.I)),
    ("Meeting", re.compile(r"\b(meeting|call|sync|standup|stand-up|discussion|demo)\b", re.I)),
    ("Investigation", re.compile(r"\b(investigat\w*|debug\w*|root cause|analy[sz]\w*|looked into|looking into)\b", re.I)),
    ("Research", re.compile(r"\b(research\w*|explor\w*|evaluat\w*|poc|spike)\b", re.I)),
    ("Learning", re.compile(r"\b(learn\w*|course|training|read up)\b", re.I)),
    ("Planning", re.compile(r"\b(plan\w*|estimat\w*|roadmap|groom\w*)\b", re.I)),
    ("Support", re.compile(r"\b(support\w*|helped|assist\w*|ticket)\b", re.I)),
    ("Enhancement", re.compile(r"\b(improv\w*|enhanc\w*|refactor\w*|optimi[sz]\w*|added|add)\b", re.I)),
    ("Development", re.compile(r"\b(implement\w*|develop\w*|built|build|creat\w*|removed|integrat\w*|wrote|code)\b", re.I)),
]
_DONE_RE = re.compile(r"\b(done|completed?|finished|fixed|added|removed|implemented|created|built|deployed|passed|merged|resolved|updated|wrote|migrated|configured)\b", re.I)


def _sentence(text: str) -> str:
    text = _BULLET_RE.sub("", text).strip()
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    return text if text[-1] in ".!?" else text + "."


def _note_lines(text: str | None) -> list[str]:
    return [line for line in (_BULLET_RE.sub("", raw).strip() for raw in (text or "").splitlines()) if line]


def guess_category(text: str) -> str | None:
    for category, pattern in _CATEGORY_KEYWORDS:
        if pattern.search(text):
            return category
    return None


def guess_status(text: str) -> str | None:
    if _BLOCK_RE.search(text):
        return "Blocked"
    if _NEXT_RE.match(text):
        return "Planned"
    if _PROGRESS_RE.search(text):
        return "In Progress"
    if _DONE_RE.search(text) or _QA_RE.search(text):
        return "Completed"
    return None


class LocalProvider(AIProvider):
    """Builds the report purely from the recorded inputs. It never adds information."""

    name = "local"

    def __init__(self, model: str = ""):
        super().__init__(model or "rule-based")

    def generate_eod(self, context: dict, options: GenerationOptions | dict | str | None = None) -> EodDraft:
        options = GenerationOptions.from_any(options)
        draft = EodDraft()
        completed: list[str] = []
        in_progress: list[str] = []
        workstreams: dict[str, list[str]] = {}

        for entry in context.get("entries", []):
            text = self._with_details(_sentence(entry["description"]), entry, context, options.length)
            status = entry.get("status")
            if _QA_RE.search(text) and entry.get("category") in (None, "Testing"):
                draft.quality_assurance.append(text)
                continue
            if status == "Blocked":
                draft.blockers.append(text)
                continue
            if status == "Planned":
                draft.next_steps.append(text)
                continue
            if status in ("In Progress", "Deferred"):
                in_progress.append(f"{text[:-1]} (in progress)." if status == "In Progress" else f"{text[:-1]} (deferred).")
            else:
                completed.append(text)
            workstreams.setdefault(entry.get("project") or context.get("project") or "General", []).append(
                in_progress[-1] if status in ("In Progress", "Deferred") else text
            )

        opener = ""
        for line in _note_lines(context.get("quick_notes")):
            text = _sentence(line)
            if _WORKED_ON_RE.match(line) and not opener:
                opener = text
                continue
            if _NEXT_RE.match(line):
                draft.next_steps.append(_sentence(_NEXT_RE.sub("", line)) or text)
            elif _ASK_RE.search(line):
                draft.asks.append(text)
            elif _BLOCK_RE.search(line):
                draft.blockers.append(text)
            elif _QA_RE.search(line):
                draft.quality_assurance.append(text)
            elif _PROGRESS_RE.search(line):
                in_progress.append(text)
                workstreams.setdefault(context.get("project") or "General", []).append(text)
            else:
                completed.append(text)

        for blocker in context.get("blockers", []):
            text = _sentence(blocker["description"])
            extra = []
            if blocker.get("dependency"):
                extra.append(f"dependency: {blocker['dependency']}")
            if options.length == "detailed":
                if blocker.get("identified_date"):
                    extra.append(f"raised {blocker['identified_date']}")
                if blocker.get("expected_resolution"):
                    extra.append(f"target resolution {blocker['expected_resolution']}")
            if extra:
                text = f"{text[:-1]} ({'; '.join(extra)})."
            draft.blockers.append(text)
        for dep in context.get("dependencies", []):
            text = _sentence(dep["description"])
            if dep.get("owner"):
                text = f"{text[:-1]} (owner: {dep['owner']})."
            (draft.asks if dep.get("type") in ("Approval", "Decision", "Access", "Information") else draft.blockers).append(text)

        draft.next_steps += [_sentence(l) for l in _note_lines(context.get("next_steps"))]
        draft.quality_assurance += [_sentence(l) for l in _note_lines(context.get("metrics"))]
        draft.key_deliverables = completed
        length = options.length
        if length in ("long", "detailed") and workstreams:
            draft.workstreams = [{"title": title, "items": items} for title, items in workstreams.items()]
        elif len(workstreams) > 1:
            draft.workstreams = [{"title": title, "items": items} for title, items in workstreams.items()]
        elif in_progress:
            draft.workstreams = [{"title": "In Progress", "items": in_progress}]
        if length == "detailed":
            # Detailed reports also carry the meetings and learnings the user recorded.
            for title, key in (("Meetings", "meetings"), ("Learnings", "learnings")):
                lines = [_sentence(l) for l in _note_lines(context.get(key))]
                if lines:
                    draft.workstreams.append({"title": title, "items": lines})
        if length == "short":
            draft.workstreams = []

        for key in ("key_deliverables", "quality_assurance", "blockers", "asks", "next_steps"):
            setattr(draft, key, list(dict.fromkeys(getattr(draft, key))))
        if options.tone in ("executive", "corporate"):
            draft = self._executive_wording(draft)  # before the snapshot, so its highlights match the bullets
        draft.executive_snapshot = self._snapshot(context, opener, draft, bool(in_progress), options)
        if length == "short":
            # Short: the most important items only. Blockers and asks are never trimmed.
            for key in ("key_deliverables", "quality_assurance", "next_steps"):
                items = getattr(draft, key)
                if len(items) > _SHORT_LIMIT:
                    setattr(draft, key, items[:_SHORT_LIMIT] + ["Further items are recorded in the work log."])
        return clean_draft(draft)

    @staticmethod
    def _with_details(text: str, entry: dict, context: dict, length: str) -> str:
        """Long and detailed reports carry the recorded category, project and time of each entry."""
        if length not in ("long", "detailed"):
            return text
        extra = [entry.get("category")] if entry.get("category") else []
        if length == "detailed":
            if entry.get("project") and entry.get("project") != context.get("project"):
                extra.append(entry["project"])
            if entry.get("time"):
                extra.append(entry["time"])
        return f"{text[:-1]} ({', '.join(extra)})." if extra else text

    @staticmethod
    def _executive_wording(draft: EodDraft) -> EodDraft:
        """Formal verb choices that keep the meaning of what the user wrote (e.g. "added" → "Introduced")."""
        def lift(value: str) -> str:
            for pattern, replacement in _EXECUTIVE_VERBS:
                new, count = pattern.subn(replacement, value, count=1)
                if count:
                    return new[0].upper() + new[1:]
            return value

        return EodDraft(
            executive_snapshot=draft.executive_snapshot,
            key_deliverables=[lift(v) for v in draft.key_deliverables],
            workstreams=[{"title": ws["title"], "items": [lift(i) for i in ws["items"]]} for ws in draft.workstreams],
            quality_assurance=[lift(v) for v in draft.quality_assurance],
            blockers=draft.blockers,
            asks=[lift(v) for v in draft.asks],
            next_steps=[lift(v) for v in draft.next_steps],
        )

    @staticmethod
    def _snapshot(context: dict, opener: str, draft: EodDraft, has_progress: bool, options: GenerationOptions) -> str:
        """States what the report covers without deriving counts or outcomes the user did not write."""
        if options.tone == "corporate":
            return LocalProvider._corporate_snapshot(context, opener, draft, has_progress, options)
        project = context.get("project")
        executive = options.tone == "executive"
        if opener:
            first = opener
        elif project:
            first = f"Today's focus was the {project} workstream." if executive else f"Worked on {project}."
        else:
            first = "Summary of today's documented work." if executive else ""
        if options.length == "short":
            return first or "Summary of today's documented work."

        covered = [label for label, present in (
            ("completed deliverables", bool(draft.key_deliverables)),
            ("work in progress", has_progress),
            ("testing and validation", bool(draft.quality_assurance)),
            ("open blockers", bool(draft.blockers)),
            ("pending asks", bool(draft.asks)),
            ("next steps", bool(draft.next_steps)),
        ) if present]
        if not covered:
            return first
        listed = covered[0] if len(covered) == 1 else ", ".join(covered[:-1]) + " and " + covered[-1]
        second = f"Progress spans {listed}." if executive else f"This update covers {listed}."
        sentences = [first, second]
        if options.length in ("long", "detailed") and draft.key_deliverables:
            highlights = [d.rstrip(".") for d in draft.key_deliverables[:2]]
            lead = "Key outcomes include" if executive else "Highlights include"
            joined = highlights[0] if len(highlights) == 1 else f"{highlights[0]} and {highlights[1][0].lower()}{highlights[1][1:]}"
            sentences.append(f"{lead} {joined[0].lower()}{joined[1:]}.")
        if options.length == "detailed" and (draft.blockers or draft.asks):
            sentences.append("Open dependencies and approvals requiring stakeholder attention are listed below."
                             if executive else "Open blockers and asks are listed below.")
        return " ".join(s for s in sentences if s).strip()

    @staticmethod
    def _corporate_snapshot(context: dict, opener: str, draft: EodDraft, has_progress: bool, options: GenerationOptions) -> str:
        """Corporate-jargon framing. Only phrases that describe the update itself are used here; terms that
        assert facts (go-live, maker-checker, T-1, ring-fenced ...) are left to the AI provider, which may use
        them only when the recorded work supports them."""
        project = context.get("project")
        scope = f"the {project} workstream" if project else "today's priorities"
        sentences = [f"Circling back with today's EOD to level-set on {scope}."]
        if opener and not project:
            sentences.append(opener)
        if options.length == "short":
            if draft.key_deliverables:
                sentences[0] = f"Circling back to level-set on {scope}: we moved the needle on the key deliverables below."
            return sentences[0]

        if draft.key_deliverables:
            sentences.append("We moved the needle on the core deliverables, keeping the north star in view without trying to boil the ocean.")
        elif has_progress:
            sentences.append("Work is in flight against the north star, scoped tightly so we are not boiling the ocean.")
        if options.length in ("long", "detailed") and draft.key_deliverables:
            highlights = [d.rstrip(".") for d in draft.key_deliverables[:2]]
            joined = highlights[0] if len(highlights) == 1 else f"{highlights[0]} and {highlights[1][0].lower()}{highlights[1][1:]}"
            sentences.append(f"Double-clicking on the highlights: {joined[0].lower()}{joined[1:]}.")
        if draft.blockers or draft.asks:
            sentences.append("Open dependencies and asks are called out below; happy to take any of these offline.")
        sentences.append("Ping me if you would like to double-click on anything.")
        return " ".join(sentences)

    def categorize(self, text: str) -> list[dict]:
        items, after_signoff = [], False
        for line in _note_lines(text):
            if _SIGNOFF_RE.match(line.strip()):
                after_signoff = True
                continue
            if is_not_work(line) or (after_signoff and len(line.split()) <= 4):
                continue  # greetings, headings, sign-offs and the name under them
            items.append({"description": _sentence(line).rstrip("."), "category": guess_category(line), "status": guess_status(line)})
        return items

    def summarize(self, text: str) -> str:
        lines = _note_lines(text)
        return "\n".join(f"- {_sentence(l)}" for l in lines[:40])


# --------------------------------------------------------------------------
# Groq provider (OpenAI-compatible chat completions, e.g. Qwen models)
# --------------------------------------------------------------------------

_THINK_RE = re.compile(r"<think>.*?</think>", re.S | re.I)


def _extract_json(text: str) -> dict:
    """Parse the model's JSON reply, tolerating stray reasoning tags or prose around the object."""
    text = _THINK_RE.sub("", text or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I).strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        start, end = text.find("{"), text.rfind("}")
        if start < 0 or end <= start:
            raise AIError("The AI provider returned an unreadable response. Please retry.") from None
        try:
            data = json.loads(text[start:end + 1])
        except json.JSONDecodeError as exc:
            raise AIError("The AI provider returned an unreadable response. Please retry.") from exc
    if not isinstance(data, dict):
        raise AIError("The AI provider returned an unexpected response.")
    return data


class GroqProvider(AIProvider):
    """Groq-hosted open models through the OpenAI-compatible chat completions API.

    Qwen reasoning models run with reasoning hidden (required for JSON mode) and, by default,
    reasoning effort "none" for fast, direct answers. The JSON schema is given in the prompt and the
    reply is validated; house style (no em/en dashes) is enforced afterwards.
    """

    name = "groq"
    default_model = "qwen/qwen3.8-27b"
    default_base_url = "https://api.groq.com/openai/v1"

    def __init__(self, api_key: str = "", model: str = "", base_url: str = "", timeout: int = 120,
                 reasoning_effort: str = "none", transport=None):
        super().__init__(model or self.default_model)
        import httpx

        self._httpx = httpx
        self.api_key = api_key
        self.reasoning_effort = reasoning_effort
        self.client = httpx.Client(base_url=(base_url or self.default_base_url).rstrip("/"), timeout=float(timeout),
                                   transport=transport)

    @property
    def _is_qwen_reasoning(self) -> bool:
        model = self.model.lower()
        return "qwen3" in model or "qwq" in model

    def _payload(self, system: str, user_content: str, max_tokens: int, json_mode: bool) -> dict:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user_content}],
            "temperature": 0.3,
            "max_completion_tokens": max_tokens,
        }
        if json_mode:
            payload["response_format"] = {"type": "json_object"}
        if self._is_qwen_reasoning:
            payload["reasoning_format"] = "hidden"
            if self.reasoning_effort:
                payload["reasoning_effort"] = self.reasoning_effort
        return payload

    def _post(self, payload: dict) -> dict:
        httpx = self._httpx
        try:
            response = self.client.post("/chat/completions", json=payload, headers={"Authorization": f"Bearer {self.api_key}"})
        except httpx.TimeoutException as exc:
            raise AIError("The AI provider took too long to respond. Please retry.") from exc
        except httpx.HTTPError as exc:
            raise AIError("Could not reach the AI provider. Check network connectivity.") from exc
        if response.status_code == 200:
            return response.json()
        try:
            error = response.json().get("error") or {}
        except ValueError:
            error = {}
        message, code = str(error.get("message") or ""), str(error.get("code") or "")
        if response.status_code == 401:
            raise AIError("Groq rejected the API key. Check AI_API_KEY in backend/.env.")
        if response.status_code == 404 or code == "model_not_found":
            raise AIError(f"The AI model '{self.model}' is not available on Groq. Check AI_MODEL in backend/.env.")
        if response.status_code == 429:
            raise AIError("Groq is rate limiting requests. Please retry in a minute.")
        if response.status_code == 400:
            raise _GroqBadRequest(code, message)
        raise AIError(f"The AI provider returned an error ({response.status_code}). Please retry.")

    def _json_call(self, system: str, user_content: str, schema: dict, max_tokens: int = 4096) -> dict:
        if not self.api_key:
            raise AIError("The Groq API key is missing. Set AI_API_KEY in backend/.env and restart the backend.")
        system = (f"{system}\n\nRespond with a single JSON object only, no prose, matching this JSON Schema:\n"
                  f"{json.dumps(schema, separators=(',', ':'))}")
        try:
            data = self._post(self._payload(system, user_content, max_tokens, json_mode=True))
        except _GroqBadRequest as exc:
            if exc.code != "json_validate_failed":
                raise AIError(f"The AI provider rejected the request: {exc.message or exc.code}") from exc
            # The model drifted from strict JSON; retry once without JSON mode and parse leniently.
            try:
                data = self._post(self._payload(system, user_content, max_tokens, json_mode=False))
            except _GroqBadRequest as retry_exc:
                raise AIError(f"The AI provider rejected the request: {retry_exc.message or retry_exc.code}") from retry_exc
        choice = (data.get("choices") or [{}])[0]
        if choice.get("finish_reason") == "length":
            raise AIError("The AI response was cut off. Try a shorter length or retry.")
        return _extract_json((choice.get("message") or {}).get("content") or "")

    def generate_eod(self, context: dict, options: GenerationOptions | dict | str | None = None) -> EodDraft:
        options = GenerationOptions.from_any(options)
        prompt = (
            f"{options.prompt()}\n\n"
            "Here is the work the user documented. Produce the EOD sections as JSON.\n\n"
            f"<documented_work>\n{json.dumps(context, indent=2, ensure_ascii=False)}\n</documented_work>"
        )
        draft = EodDraft.from_dict(self._json_call(EOD_SYSTEM_PROMPT, prompt, EOD_SCHEMA))
        if draft.is_empty():
            raise AIError("The AI provider returned an empty report. Please retry.")
        return clean_draft(draft)

    def categorize(self, text: str) -> list[dict]:
        data = self._json_call(CATEGORIZE_SYSTEM_PROMPT, f"<notes>\n{text}\n</notes>", CATEGORIZE_SCHEMA)
        items = []
        for item in data.get("items") or []:
            if not isinstance(item, dict):
                continue
            desc = str(item.get("description") or "").strip()
            if desc and not is_not_work(desc):
                items.append({
                    "description": remove_dashes(desc),
                    "category": item.get("category") if item.get("category") in WORK_CATEGORIES else None,
                    "status": item.get("status") if item.get("status") in WORK_STATUSES else None,
                })
        return items

    def summarize(self, text: str) -> str:
        schema = {"type": "object", "properties": {"summary": {"type": "string"}}, "required": ["summary"], "additionalProperties": False}
        data = self._json_call(SUMMARY_SYSTEM_PROMPT, f"<documented_work>\n{text}\n</documented_work>", schema)
        return remove_dashes(str(data.get("summary") or "").strip())


class _GroqBadRequest(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message or code)
        self.code = code
        self.message = message


PROVIDERS = {"local": LocalProvider, "groq": GroqProvider}


def create_ai_provider(settings) -> AIProvider:
    name = settings.AI_PROVIDER
    if name == "local":
        return LocalProvider()
    if name == "groq":
        return GroqProvider(
            api_key=settings.AI_API_KEY, model=settings.AI_MODEL, base_url=settings.AI_BASE_URL,
            timeout=settings.AI_TIMEOUT_SECONDS, reasoning_effort=settings.AI_REASONING_EFFORT,
        )
    raise RuntimeError(f"Unsupported AI_PROVIDER '{name}'. Supported: {', '.join(PROVIDERS)}")


# --------------------------------------------------------------------------
# Fabrication guard
# --------------------------------------------------------------------------

_NUMBER_RE = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?%?")


def unsupported_numbers(generated: str, source: str) -> list[str]:
    """Numbers present in the generated report that never appear in the user's input."""
    source_numbers = {n.rstrip("%").replace(",", "") for n in _NUMBER_RE.findall(source)}
    flagged = []
    for number in _NUMBER_RE.findall(generated):
        bare = number.rstrip("%").replace(",", "")
        if bare not in source_numbers and number not in flagged:
            flagged.append(number)
    return flagged
