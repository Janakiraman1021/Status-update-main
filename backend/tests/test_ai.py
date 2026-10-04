import json
from types import SimpleNamespace

import httpx
import pytest

from app.services.ai_service import (
    AIError, EodDraft, GroqProvider, LocalProvider, create_ai_provider, unsupported_numbers,
)
from app.services.eod_renderer import body_to_html, build_subject, draft_to_body
from conftest import make_settings


def test_local_provider_never_upgrades_completion_state():
    context = {
        "project": "Azure Migration",
        "quick_notes": "investigated an issue with login\nlooked into Azure deployment\nfixed date validation",
    }
    draft = LocalProvider().generate_eod(context, {"tone": "professional"})
    text = draft_to_body(draft, "Janakiraman").lower()
    assert "investigated an issue with login" in text
    assert "looked into azure deployment" in text
    for word in ("resolved", "stabilized", "stabilised", "successfully"):
        assert word not in text


def test_local_provider_only_uses_given_numbers():
    context = {"quick_notes": "94 tests passed\nneed DBA approval", "project": "Statements Dashboard"}
    body = draft_to_body(LocalProvider().generate_eod(context, {"tone": "professional"}), "J")
    assert unsupported_numbers(body, "94 tests passed need DBA approval") == []


def test_local_provider_sections():
    context = {
        "project": "Statements Dashboard",
        "entries": [
            {"description": "Removed statement selector", "status": "Completed", "category": "Development"},
            {"description": "Dark mode", "status": "In Progress", "category": "Enhancement"},
            {"description": "Regression tests passed", "status": "Completed", "category": "Testing"},
        ],
        "blockers": [{"description": "Waiting on date column decision", "status": "Open", "dependency": "Business team"}],
        "dependencies": [{"description": "Access to prod replica", "type": "Access", "owner": "DBA team", "status": "Open"}],
        "next_steps": "Deploy to UAT",
    }
    draft = LocalProvider().generate_eod(context, {"tone": "professional"})
    assert draft.key_deliverables == ["Removed statement selector."]
    assert draft.workstreams == [{"title": "In Progress", "items": ["Dark mode (in progress)."]}]
    assert draft.quality_assurance == ["Regression tests passed."]
    assert draft.blockers == ["Waiting on date column decision (dependency: Business team)."]
    assert draft.asks == ["Access to prod replica (owner: DBA team)."]
    assert draft.next_steps == ["Deploy to UAT."]
    assert draft.executive_snapshot == (
        "Worked on Statements Dashboard. This update covers completed deliverables, work in progress, "
        "testing and validation, open blockers, pending asks and next steps."
    )


def test_feature_work_mentioning_validation_is_a_deliverable():
    draft = LocalProvider().generate_eod({"quick_notes": "Implemented date validation.\n94 tests passed."})
    assert draft.key_deliverables == ["Implemented date validation."]
    assert draft.quality_assurance == ["94 tests passed."]


def test_categorize_skips_email_scaffolding():
    pasted = ("Subject: EOD Status Update | 03 Oct 2026\nHi,\nTrust you are doing well.\nEXECUTIVE SNAPSHOT\n"
              "Removed statement selector\nKEY DELIVERABLES\n- 94 tests passed\nThanks and regards,\nJanakiraman K")
    items = LocalProvider().categorize(pasted)
    assert [i["description"] for i in items] == ["Removed statement selector", "94 tests passed"]


def test_local_provider_uses_worked_on_line_as_opener():
    draft = LocalProvider().generate_eod({"quick_notes": "worked on Statements Dashboard\nremoved selector"}, {"tone": "professional"})
    assert draft.executive_snapshot == "Worked on Statements Dashboard. This update covers completed deliverables."
    assert draft.key_deliverables == ["Removed selector."]


def test_unsupported_numbers():
    assert unsupported_numbers("94 tests passed, 100% coverage", "94 tests passed") == ["100%"]
    assert unsupported_numbers("EOD 03 Oct 2026", "2026-10-03 03 Oct 2026") == []


def test_renderer_html_structure():
    draft = EodDraft(executive_snapshot="Worked on <script>alert(1)</script>.", key_deliverables=["A & B"],
                     workstreams=[{"title": "Statements", "items": ["Item one"]}])
    body = draft_to_body(draft, "Jana")
    assert "Statements:\n- Item one" in body
    html = body_to_html(body, build_subject("03 Oct 2026", "Dash"))
    assert "&lt;script&gt;" in html and "<script>" not in html
    assert "A &amp; B" in html
    assert "<i>Statements:</i>" in html
    assert build_subject("03 Oct 2026", None) == "EOD Status Update | 03 Oct 2026"


def test_dashes_are_removed_from_generated_reports():
    from app.services.ai_service import clean_draft, remove_dashes

    assert remove_dashes("Delivered the forms — ahead of review") == "Delivered the forms, ahead of review"
    assert remove_dashes("Sprint 3–4 scope") == "Sprint 3-4 scope"
    assert remove_dashes("Statement forms – rationalised.") == "Statement forms, rationalised."
    draft = clean_draft(EodDraft(executive_snapshot="Done — all good", key_deliverables=["— Removed selector"]))
    assert draft.executive_snapshot == "Done, all good" and draft.key_deliverables == ["Removed selector"]
    body = draft_to_body(LocalProvider().generate_eod({"quick_notes": "fixed login — added tests"}), "J")
    assert "—" not in body and "–" not in body


def test_length_options_change_the_local_report():
    context = {
        "project": "Dashboard",
        "entries": [{"description": "Removed selector", "status": "Completed", "project": "Dashboard"},
                    {"description": "Dark mode", "status": "In Progress", "project": "Dashboard"}],
        "meetings": "Sprint review with product",
    }
    short = LocalProvider().generate_eod(context, {"length": "short"})
    detailed = LocalProvider().generate_eod(context, {"length": "detailed"})
    assert short.workstreams == []
    assert [ws["title"] for ws in detailed.workstreams] == ["Dashboard", "Meetings"]


def test_local_lengths_produce_visibly_different_reports():
    context = {
        "project": "Statements Dashboard",
        "quick_notes": "removed statement selector\nadded dark mode\nimplemented date validation\ncreated access schema\nneed DBA approval",
        "entries": [{"description": "Refactored filters", "status": "Completed", "category": "Enhancement", "time": "10:00 AM",
                     "project": "Statements Dashboard"}],
    }
    pro = {"tone": "professional"}
    short = LocalProvider().generate_eod(context, {**pro, "length": "short"})
    medium = LocalProvider().generate_eod(context, {**pro, "length": "standard"})
    long = LocalProvider().generate_eod(context, {**pro, "length": "long"})
    detailed = LocalProvider().generate_eod(context, {**pro, "length": "detailed"})

    assert len(short.key_deliverables) == 4 and short.key_deliverables[-1] == "Further items are recorded in the work log."
    assert short.executive_snapshot.count(".") == 1  # one-sentence snapshot
    assert short.asks == ["Need DBA approval."]  # asks are never trimmed
    assert len(medium.key_deliverables) == 5
    assert "Refactored filters (Enhancement)." in long.key_deliverables and "Highlights include" in long.executive_snapshot
    assert "Refactored filters (Enhancement, 10:00 AM)." in detailed.key_deliverables
    assert "Open blockers and asks are listed below." in detailed.executive_snapshot
    bodies = {draft_to_body(d, "J") for d in (short, medium, long, detailed)}
    assert len(bodies) == 4


def test_local_executive_tone_uses_formal_synonyms_only():
    context = {"project": "Dashboard", "quick_notes": "added dark mode\nremoved selector\ninvestigated login issue\nneed DBA approval"}
    executive = LocalProvider().generate_eod(context, {"tone": "executive"})
    assert "Introduced dark mode." in executive.key_deliverables
    assert "Retired selector." in executive.key_deliverables
    assert executive.asks == ["Pending: DBA approval."]
    assert executive.executive_snapshot.startswith("Today's focus was the Dashboard workstream.")
    text = draft_to_body(executive, "J").lower()
    assert "investigated login issue" in text and "resolved" not in text  # completion state preserved


def test_local_corporate_tone_uses_jargon_without_inventing_facts():
    context = {"project": "Statements Dashboard", "quick_notes": "added dark mode\nremoved selector\nneed DBA approval"}
    draft = LocalProvider().generate_eod(context, {"tone": "corporate", "length": "long"})
    snapshot = draft.executive_snapshot
    for phrase in ("Circling back", "level-set", "moved the needle", "north star", "boil the ocean", "Double-clicking", "offline", "Ping me"):
        assert phrase in snapshot, phrase
    # Fact-asserting jargon is never added by the local writer
    text = draft_to_body(draft, "J").lower()
    for claim in ("go-live", "maker-checker", "t-1", "ring-fenced", "blast radius", "single pane", "defense-in-depth"):
        assert claim not in text, claim
    assert "Introduced dark mode." in draft.key_deliverables
    short = LocalProvider().generate_eod(context, {"tone": "corporate", "length": "short"})
    assert short.executive_snapshot.startswith("Circling back to level-set on the Statements Dashboard workstream")


def test_branded_html_email():
    from app.services.eod_renderer import EmailTheme

    body = draft_to_body(EodDraft(executive_snapshot="Worked on the dashboard.", key_deliverables=["Removed selector."],
                                  next_steps=["Deploy to UAT."]), "Janakiraman")
    html = body_to_html(body, "EOD Status Update | 03 Oct 2026", EmailTheme(),
                        {"date_label": "03 October 2026", "project": "Statements Dashboard", "sender": "Janakiraman"})
    # Plain, Outlook-style email: title-case bold headings, real bullets, normal signature
    assert [h for h in ("Executive Snapshot", "Key Deliverables", "Next Steps") if f">{h}</h3>" in html] == [
        "Executive Snapshot", "Key Deliverables", "Next Steps"]
    assert "<li" in html and "Removed selector." in html and "Deploy to UAT." in html
    assert "Thanks and regards,<br><b>Janakiraman</b>" in html
    # No template decoration: no banners, summary strip, tables, colour blocks, subject repeat or footer
    for decoration in ("<table", "bgcolor=\"#0", "Prepared by", "End of Day Status Update", "confidential", "EOD Status Update | 03"):
        assert decoration not in html.split("</title>", 1)[1], decoration
    assert 'name="viewport"' in html and "max-width:720px" in html


def test_heading_title_case_keeps_acronyms():
    from app.services.eod_renderer import _title_case

    assert _title_case("QUALITY ASSURANCE AND VALIDATION") == "Quality Assurance and Validation"
    assert _title_case("BLOCKERS / DEPENDENCIES") == "Blockers / Dependencies"
    assert _title_case("UAT AND QA SIGN-OFF") == "UAT and QA Sign-off"


def test_logo_is_embedded_inline_in_sent_email(tmp_path):
    import base64

    from app.services.email_service import InlineImage, MemoryProvider, OutgoingEmail
    from app.services.eod_renderer import LOGO_CID, EmailTheme

    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==")
    logo = tmp_path / "logo.png"
    logo.write_bytes(png)
    theme = EmailTheme(logo_path=str(logo))
    assert theme.logo_image() == (png, "image/png")
    assert theme.logo_data_uri().startswith("data:image/png;base64,")

    html = body_to_html("Hi,\n\nKEY DELIVERABLES\n- Done.\n\nThanks and regards,\nJanakiraman", "EOD", theme, logo_src=f"cid:{LOGO_CID}")
    assert f'src="cid:{LOGO_CID}"' in html
    provider = MemoryProvider()
    mime = provider.build_mime(OutgoingEmail(to=["a@b.com"], subject="EOD", html=html, text="Hi",
                                             inline_images=[InlineImage(LOGO_CID, png, "image/png")]))
    parts = list(mime.walk())
    image = next(p for p in parts if p.get_content_type() == "image/png")
    assert image["Content-ID"] == f"<{LOGO_CID}>" and image.get_payload(decode=True) == png
    assert any(p.get_content_type() == "multipart/related" for p in parts)
    assert any(p.get_content_type() == "text/plain" for p in parts)


def test_missing_or_unsafe_logo_falls_back_to_text(tmp_path):
    from app.services.eod_renderer import EmailTheme

    assert EmailTheme(logo_path=str(tmp_path / "missing.png")).logo_image() is None
    (tmp_path / "logo.svg").write_text("<svg/>")
    assert EmailTheme(logo_path=str(tmp_path / "logo.svg")).logo_image() is None  # SVG is not reliable in email
    html = body_to_html("Hi,\n\nThanks and regards,\nJ", "EOD", EmailTheme())
    assert "<img" not in html  # without a logo file the signature is text only


def test_theme_from_settings_rejects_bad_values():
    from types import SimpleNamespace

    from app.services.eod_renderer import EmailTheme

    theme = EmailTheme.from_settings(SimpleNamespace(EMAIL_BRAND_NAME="Acme", EMAIL_BRAND_PRIMARY="red",
                                                     EMAIL_BRAND_ACCENT="#00FF00", EMAIL_BRAND_SOFT="",
                                                     EMAIL_BRAND_LOGO_URL="http://insecure/logo.png"))
    assert theme.brand_name == "Acme" and theme.accent == "#00FF00"
    assert theme.primary == EmailTheme().primary and theme.logo_url == ""


class GroqStub:
    """Fake Groq chat-completions endpoint: returns queued (status, body) pairs and records requests."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.requests: list[dict] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append({"url": str(request.url), "headers": dict(request.headers), "json": json.loads(request.content)})
        status, body = self.responses.pop(0)
        return httpx.Response(status, json=body)


def _completion(content, finish_reason="stop"):
    text = content if isinstance(content, str) else json.dumps(content)
    return 200, {"choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": finish_reason}]}


def _groq(*responses, model="qwen/qwen3.8-27b", api_key="gsk_test"):
    stub = GroqStub(*responses)
    return GroqProvider(api_key=api_key, model=model, transport=httpx.MockTransport(stub)), stub


EOD_OK = {"executive_snapshot": "Worked on the dashboard.", "key_deliverables": ["Removed selector."], "workstreams": [],
          "quality_assurance": ["94 tests passed."], "blockers": [], "asks": ["DBA approval required."], "next_steps": []}


def test_groq_provider_request_and_parsing():
    provider, stub = _groq(_completion(EOD_OK))
    draft = provider.generate_eod({"quick_notes": "removed selector"}, "concise")
    assert draft.key_deliverables == ["Removed selector."]
    request = stub.requests[0]
    assert request["url"] == "https://api.groq.com/openai/v1/chat/completions"
    assert request["headers"]["authorization"] == "Bearer gsk_test"
    body = request["json"]
    assert body["model"] == "qwen/qwen3.8-27b"
    assert body["response_format"] == {"type": "json_object"}
    assert body["reasoning_format"] == "hidden" and body["reasoning_effort"] == "none"
    system, user = body["messages"][0]["content"], body["messages"][1]["content"]
    assert "Never invent information." in system and "JSON Schema" in system and "Never use em dashes" in system
    assert "Length: SHORT" in user  # legacy "concise" maps to the short length


def test_groq_prompt_carries_length_and_tone():
    provider, stub = _groq(_completion(EOD_OK))
    provider.generate_eod({"quick_notes": "x"}, {"length": "detailed", "tone": "corporate"})
    user = stub.requests[0]["json"]["messages"][1]["content"]
    assert "Length: DETAILED" in user and "Tone: CORPORATE" in user and "never claim a go-live" in user


def test_groq_non_qwen_models_skip_reasoning_params():
    provider, stub = _groq(_completion(EOD_OK), model="llama-3.1-8b-instant")
    provider.generate_eod({"quick_notes": "x"})
    body = stub.requests[0]["json"]
    assert "reasoning_format" not in body and "reasoning_effort" not in body


def test_groq_tolerates_think_tags_fences_and_dashes():
    messy = "<think>planning…</think>\n```json\n" + json.dumps({**EOD_OK, "executive_snapshot": "Shipped forms — ahead of review."}) + "\n```"
    provider, _ = _groq(_completion(messy))
    draft = provider.generate_eod({"quick_notes": "x"})
    assert draft.executive_snapshot == "Shipped forms, ahead of review."


def test_groq_retries_without_json_mode_on_json_validation_failure():
    provider, stub = _groq(
        (400, {"error": {"code": "json_validate_failed", "message": "Failed to generate JSON"}}),
        _completion("Here you go: " + json.dumps(EOD_OK)),
    )
    assert provider.generate_eod({"quick_notes": "x"}).key_deliverables == ["Removed selector."]
    assert "response_format" in stub.requests[0]["json"] and "response_format" not in stub.requests[1]["json"]


@pytest.mark.parametrize("response, message", [
    ((401, {"error": {"message": "Invalid API Key"}}), "API key"),
    ((404, {"error": {"code": "model_not_found", "message": "nope"}}), "not available on Groq"),
    ((429, {"error": {"message": "slow down"}}), "rate limiting"),
    ((500, {"error": {"message": "boom"}}), r"error \(500\)"),
    (_completion(EOD_OK, finish_reason="length"), "cut off"),
    (_completion("not json at all"), "unreadable"),
    (_completion({**{k: [] for k in EOD_OK}, "executive_snapshot": ""}), "empty report"),
])
def test_groq_errors_become_friendly_messages(response, message):
    provider, _ = _groq(response)
    with pytest.raises(AIError, match=message):
        provider.generate_eod({"quick_notes": "x"})


def test_groq_missing_key_fails_clearly_without_calling_the_api():
    provider, stub = _groq(api_key="")
    with pytest.raises(AIError, match="AI_API_KEY"):
        provider.generate_eod({"quick_notes": "x"})
    assert stub.requests == []


def test_groq_categorize_filters_unknown_values_and_scaffolding():
    payload = {"items": [{"description": "Fixed login bug", "category": "Bug Fix", "status": "Completed"},
                         {"description": "Thing", "category": "Nonsense", "status": None},
                         {"description": "Thanks and regards,", "category": None, "status": None}]}
    provider, _ = _groq(_completion(payload))
    assert provider.categorize("fixed login bug\nthing") == [
        {"description": "Fixed login bug", "category": "Bug Fix", "status": "Completed"},
        {"description": "Thing", "category": None, "status": None},
    ]


def test_provider_factory():
    assert create_ai_provider(make_settings(AI_PROVIDER="local")).name == "local"
    groq = create_ai_provider(make_settings(AI_PROVIDER="groq", AI_API_KEY="k", AI_MODEL=""))
    assert groq.name == "groq" and groq.model == "qwen/qwen3.8-27b"
    with pytest.raises(RuntimeError):
        create_ai_provider(make_settings(AI_PROVIDER="anthropic"))
