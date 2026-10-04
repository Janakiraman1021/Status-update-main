"""Render EOD drafts to an editable plain-text body and to a clean, Outlook-style HTML email.

Body conventions (kept simple so users can edit in a plain textarea):
  - A line in UPPER CASE is a section heading.
  - Lines starting with "- " are bullet points.
  - A line ending with ":" directly followed by bullets is a sub-heading (workstreams).
  - Blank lines separate paragraphs.
"""
from __future__ import annotations

import base64
import html
import re
from dataclasses import dataclass
from pathlib import Path

from .ai_service import EodDraft

SECTION_TITLES = {
    "executive_snapshot": "EXECUTIVE SNAPSHOT",
    "key_deliverables": "KEY DELIVERABLES",
    "workstreams": "WORKSTREAM DETAILS",
    "quality_assurance": "QUALITY ASSURANCE AND VALIDATION",
    "blockers": "BLOCKERS / DEPENDENCIES",
    "asks": "ASKS / APPROVALS",
    "next_steps": "NEXT STEPS",
}

_HEADING_RE = re.compile(r"^[A-Z0-9][A-Z0-9 /&,()'\-–]{2,80}$")
_BULLET_RE = re.compile(r"^\s*[-•*]\s+(.*)$")
_SIGNOFF_RE = re.compile(r"^(thanks( and| &)? regards|regards|best regards|warm regards|thank you)[,!.]?$", re.I)
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def build_subject(date_label: str, project_label: str | None) -> str:
    subject = f"EOD Status Update | {date_label}"
    return f"{subject} | {project_label}" if project_label else subject


def draft_to_body(draft: EodDraft, user_name: str) -> str:
    out: list[str] = ["Hi,", "", "Trust you are doing well.", ""]

    def section(title: str, lines: list[str]) -> None:
        if lines:
            out.extend([title, *lines, ""])

    if draft.executive_snapshot:
        section(SECTION_TITLES["executive_snapshot"], [draft.executive_snapshot])
    section(SECTION_TITLES["key_deliverables"], [f"- {item}" for item in draft.key_deliverables])
    if draft.workstreams:
        ws_lines: list[str] = []
        for ws in draft.workstreams:
            if ws.get("title"):
                ws_lines.append(f"{ws['title'].rstrip(':')}:")
            ws_lines.extend(f"- {item}" for item in ws["items"])
            ws_lines.append("")
        section(SECTION_TITLES["workstreams"], ws_lines[:-1])
    section(SECTION_TITLES["quality_assurance"], [f"- {item}" for item in draft.quality_assurance])
    section(SECTION_TITLES["blockers"], [f"- {item}" for item in draft.blockers])
    section(SECTION_TITLES["asks"], [f"- {item}" for item in draft.asks])
    section(SECTION_TITLES["next_steps"], [f"- {item}" for item in draft.next_steps])
    out.extend(["Thanks and regards,", user_name])
    return "\n".join(out).strip() + "\n"


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    return bool(_HEADING_RE.match(stripped)) and any(c.isalpha() for c in stripped) and stripped == stripped.upper()


# ---------------------------------------------------------------------------
# Branded HTML email
# ---------------------------------------------------------------------------

_LOGO_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif"}
_MAX_LOGO_BYTES = 1_000_000
LOGO_CID = "brand-logo"


@dataclass(frozen=True)
class EmailTheme:
    """Company branding for the EOD email (EMAIL_BRAND_* in backend/.env)."""

    brand_name: str = "Samunnati"
    legal_name: str = "Samunnati Finance Private Limited"
    primary: str = "#0B6B3A"   # title band and headings
    accent: str = "#F2A900"    # stripe, section markers and bullets
    soft: str = "#EEF6F1"      # highlighted panels
    logo_url: str = ""         # optional public https URL for the logo
    logo_path: str = ""        # optional local logo file (PNG/JPG/GIF), embedded in the email
    website: str = ""          # optional, shown in the footer
    tagline: str = "End of Day Status Update"

    @classmethod
    def from_settings(cls, settings) -> "EmailTheme":
        default = cls()

        def get(name: str) -> str:
            return (getattr(settings, name, "") or "").strip()

        def color(name: str, fallback: str) -> str:
            value = get(name)
            return value if _HEX_RE.match(value) else fallback

        logo_url = get("EMAIL_BRAND_LOGO_URL")
        website = get("EMAIL_BRAND_WEBSITE")
        return cls(
            brand_name=get("EMAIL_BRAND_NAME") or default.brand_name,
            legal_name=get("EMAIL_BRAND_LEGAL_NAME") or default.legal_name,
            primary=color("EMAIL_BRAND_PRIMARY", default.primary),
            accent=color("EMAIL_BRAND_ACCENT", default.accent),
            soft=color("EMAIL_BRAND_SOFT", default.soft),
            logo_url=logo_url if logo_url.startswith("https://") else "",
            logo_path=get("EMAIL_BRAND_LOGO_PATH"),
            website=website if website.startswith(("https://", "http://")) else "",
        )

    def logo_image(self) -> tuple[bytes, str] | None:
        """The local logo file as (bytes, mime type), or None if it is missing or unsuitable."""
        if not self.logo_path:
            return None
        path = Path(self.logo_path)
        if not path.is_absolute():
            path = Path(__file__).resolve().parents[2] / path
        mime = _LOGO_TYPES.get(path.suffix.lower())
        try:
            if mime and path.is_file() and path.stat().st_size <= _MAX_LOGO_BYTES:
                return path.read_bytes(), mime
        except OSError:
            pass
        return None

    def logo_data_uri(self) -> str:
        image = self.logo_image()
        return f"data:{image[1]};base64,{base64.b64encode(image[0]).decode('ascii')}" if image else ""


_FONT = "font-family:Calibri,'Segoe UI',Arial,Helvetica,sans-serif;"
_TEXT = "#1f1f1f"
_BODY = f"{_FONT}font-size:15px;line-height:1.5;color:{_TEXT};"

# Words kept in upper case when headings are shown in title case.
_ACRONYMS = {"EOD", "QA", "UAT", "API", "APIS", "KPI", "KPIS", "SLA", "UI", "UX", "DBA", "IT", "HR", "ETA", "MIS", "CI", "CD", "PR", "POC"}
_SMALL_WORDS = {"and", "or", "of", "the", "a", "an", "to", "for", "in", "on", "at", "by", "with"}


def _title_case(heading: str) -> str:
    """'QUALITY ASSURANCE AND VALIDATION' → 'Quality Assurance and Validation' (acronyms kept)."""
    words = []
    for index, word in enumerate(heading.split()):
        bare = re.sub(r"[^A-Za-z]", "", word)
        if bare.upper() in _ACRONYMS:
            words.append(word.upper())
        elif index and word.lower() in _SMALL_WORDS:
            words.append(word.lower())
        else:
            words.append(word[:1].upper() + word[1:].lower())
    return " ".join(words)


def _render_blocks(lines: list[str]) -> str:
    """Paragraphs, bullet lists and sub-headings ("Title:" followed by bullets), styled like a typed email."""
    parts: list[str] = []
    bullets: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph():
        if paragraph:
            parts.append(f'<p style="margin:0 0 10px 0;{_BODY}">{"<br>".join(paragraph)}</p>')
            paragraph.clear()

    def flush_bullets():
        if bullets:
            items = "".join(f'<li style="margin:0 0 4px 0;{_BODY}">{item}</li>' for item in bullets)
            parts.append(f'<ul style="margin:0 0 10px 0;padding:0 0 0 26px;">{items}</ul>')
            bullets.clear()

    for index, raw in enumerate(lines):
        line = raw.strip()
        if not line:
            flush_paragraph()
            flush_bullets()
            continue
        bullet = _BULLET_RE.match(line)
        if bullet:
            flush_paragraph()
            bullets.append(html.escape(bullet.group(1).strip()))
            continue
        flush_bullets()
        next_line = next((l for l in lines[index + 1:] if l.strip()), "")
        if line.endswith(":") and _BULLET_RE.match(next_line):
            flush_paragraph()
            parts.append(f'<p style="margin:6px 0 4px 0;{_BODY}"><i>{html.escape(line)}</i></p>')
        else:
            paragraph.append(html.escape(line))
    flush_paragraph()
    flush_bullets()
    return "".join(parts)


def _split_sections(body: str) -> tuple[list[str], list[tuple[str, list[str]]], list[str]]:
    """Split the body into (greeting lines, [(HEADING, lines)], sign-off lines)."""
    intro: list[str] = []
    sections: list[tuple[str, list[str]]] = []
    closing: list[str] = []
    for raw in body.replace("\r\n", "\n").split("\n"):
        line = raw.rstrip()
        if closing or _SIGNOFF_RE.match(line.strip()):
            closing.append(line)
        elif _is_heading(line):
            sections.append((line.strip(), []))
        elif sections:
            sections[-1][1].append(line)
        else:
            intro.append(line)
    return intro, sections, closing


def body_to_html(body: str, subject: str, theme: EmailTheme | None = None, meta: dict | None = None,
                 logo_src: str | None = None) -> str:
    """Render the EOD body as a plain, professional email, the way it would look typed in Outlook.

    No banners, boxes or colour blocks: greeting, bold section headings, simple bullets and a normal
    signature (with the company logo underneath when one is configured). A single fluid column, so it
    reads naturally on phones as well as desktop clients. `meta` is accepted for compatibility.
    `logo_src` is "cid:brand-logo" for sent emails or a data URI for previews.
    """
    theme = theme or EmailTheme()
    esc = html.escape
    intro, sections, closing = _split_sections(body)
    src = logo_src or theme.logo_url

    blocks: list[str] = []
    intro_html = _render_blocks(intro)
    if intro_html:
        blocks.append(intro_html)
    for title, lines in sections:
        content = _render_blocks(lines)
        if not content:
            continue
        blocks.append(
            f'<h3 style="margin:18px 0 6px 0;{_FONT}font-size:15px;font-weight:bold;line-height:1.4;color:{_TEXT};">'
            f'{esc(_title_case(title))}</h3>{content}'
        )

    closing_lines = [line.strip() for line in closing if line.strip()]
    if closing_lines:
        first, rest = closing_lines[0], closing_lines[1:]
        signature = f'<p style="margin:22px 0 0 0;{_BODY}">{esc(first)}'
        if rest:
            signature += "<br><b>" + "<br>".join(esc(r) for r in rest) + "</b>"
        signature += "</p>"
        if src:
            signature += (f'<p style="margin:12px 0 0 0;"><img src="{esc(src)}" alt="{esc(theme.brand_name)}" width="140" '
                          f'style="display:block;width:140px;max-width:140px;height:auto;border:0;"></p>')
        blocks.append(signature)

    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="x-apple-disable-message-reformatting">\n'
        f"<title>{esc(subject)}</title>\n"
        "<style>@media only screen and (max-width:600px){.wl-body{padding:16px !important;}}</style>\n"
        "</head>\n"
        '<body style="margin:0;padding:0;background:#ffffff;" bgcolor="#ffffff">\n'
        f'<div class="wl-body" style="max-width:720px;padding:20px 24px;{_BODY}">\n'
        + "\n".join(blocks)
        + "\n</div>\n</body>\n</html>"
    )
