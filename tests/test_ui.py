"""AE UI briefing parser, progress labels, and FastAPI routes."""

from __future__ import annotations

from google.adk.events import Event
from google.adk.sessions import InMemorySessionService
from google.genai import types
from starlette.testclient import TestClient

from agents.constants import GREETING_REPLY
from models.synthesis_output import (
    CopyReadyArtifact,
    RecommendedAction,
    SynthesisOutput,
    render_synthesis_markdown,
)
from ui.app import create_app
from ui.briefing import parse_reply
from ui.progress import status_for_author


def _event(author: str, text: str) -> Event:
    return Event(
        invocation_id="inv",
        author=author,
        content=types.Content(
            role="model", parts=[types.Part.from_text(text=text)]
        ),
    )


class FakeRunner:
    def __init__(self, events: list[Event]) -> None:
        self.events = events

    async def run_async(self, **_kwargs):  # noqa: ANN003
        for event in self.events:
            yield event


def test_parse_reply_keeps_greetings_plain() -> None:
    assert parse_reply(GREETING_REPLY) == {"kind": "plain", "text": GREETING_REPLY}


def test_parse_reply_round_trips_rendered_briefing() -> None:
    markdown = render_synthesis_markdown(
        SynthesisOutput(
            summary="7-Eleven is ready for the POS pilot briefing.",
            insights=["Priya is the champion.", "Duplicate contact still open."],
            actions=[
                RecommendedAction(
                    action="Send the 50-store pilot plan.",
                    owner="you",
                    due="this week",
                    paste="Priya — attaching the POS pilot plan.",
                )
            ],
            artifacts=[
                CopyReadyArtifact(
                    title="Follow-up email",
                    kind="email",
                    body="Hi Priya,\nSee the attached plan.",
                )
            ],
        )
    )
    parsed = parse_reply(markdown)
    assert parsed["kind"] == "briefing"
    assert parsed["summary"] == "7-Eleven is ready for the POS pilot briefing."
    assert parsed["insights"][0] == "Priya is the champion."
    assert parsed["actions"][0]["paste"].startswith("Priya")
    assert parsed["artifacts"][0]["title"] == "Follow-up email"
    assert "attached plan" in parsed["artifacts"][0]["body"]


def test_status_hides_orchestrator_and_unknown_authors() -> None:
    assert "crm" in status_for_author("crm_intelligence_specialist").lower()
    assert "policy" in status_for_author("knowledge_base_rag").lower()
    assert status_for_author("central_orchestrator") is None
    assert status_for_author("secret_debug") is None


def _client(events: list[Event]) -> TestClient:
    return TestClient(
        create_app(runner=FakeRunner(events), session_service=InMemorySessionService())
    )


def _task_id(label: str) -> str:
    from ui.catalog import TASK_MENU

    return next(
        item["id"]
        for group in TASK_MENU
        for item in group["items"]
        if item["label"] == label
    )


def _sse_events(response_text: str) -> list[dict]:
    import json

    payloads = []
    for block in response_text.split("\n\n"):
        for line in block.splitlines():
            if line.startswith("data:"):
                payloads.append(json.loads(line[5:].strip()))
    return payloads


def test_landing_links_to_workspace() -> None:
    client = _client([])
    home = client.get("/")
    assert home.status_code == 200
    assert b"Open workspace" in home.content
    assert b'id="landing"' in home.content
    assert b'id="task-menu"' in home.content
    assert b'id="chat-history"' in home.content
    assert b'id="new-chat"' in home.content
    assert home.content.find(b"Task menu") < home.content.find(b"Chat history")
    assert b'id="stop"' in home.content
    assert b'aria-label="Send"' in home.content
    assert b'id="dictate"' in home.content
    assert b'id="voice-call"' in home.content
    assert b'id="voice-call-btn"' in home.content
    assert b'id="attach"' in home.content
    assert b'id="toggle-left"' in home.content
    assert b'id="toggle-right"' in home.content
    assert b'id="filter-geos"' in home.content
    assert b'id="filter-reps"' in home.content
    assert b'id="filter-horizon"' in home.content
    assert b"Your book" in home.content
    assert b"data-theme-toggle" in home.content
    assert b"/static/sp-logo.png" in home.content
    assert b"Project Gru" in home.content
    assert b"Stuart \xe2\x80\x94 Sales Manager Assistant" in home.content
    assert b'id="query-nav"' in home.content
    app_js = client.get("/static/app.js").text
    assert 'getElementById("toggle-right")' in app_js
    assert 'id="open-workspace"' in app_js or "open-workspace" in app_js
    assert "/static/bob_confused.gif" in app_js
    assert 'classList.contains("pending")' in app_js
    assert "Stopped. Stuart cancelled this reply." in app_js
    assert "function toggleDictation" in app_js
    assert "function startCall" in app_js
    assert "data-theme-toggle" in app_js
    assert "Copy response" in app_js
    assert "function briefingText" in app_js
    assert 'CHATS_KEY = "gru-chats"' in app_js
    assert "function persistChats" in app_js
    assert "function restoreActiveChat" in app_js
    assert 'WORKSPACE_KEY = "gru-workspace-open"' in app_js
    assert "function showWorkspace" in app_js
    styles = client.get("/static/styles.css").text
    assert "--user-bubble: #fde8f3" in styles
    assert ".artifact + .artifact" in styles
    assert "html[data-theme=\"dark\"] .brand-logo" not in styles
    gif = client.get("/static/bob_confused.gif")
    assert gif.status_code == 200
    assert gif.headers["content-type"].startswith("image/gif")
    assert b"Seller Co-Pilot" not in home.content
    assert b'id="open-workspace"' in home.content
    redirected = client.get("/app", follow_redirects=False)
    assert redirected.status_code == 302
    assert redirected.headers["location"] == "/"


def test_starters_and_session_endpoints() -> None:
    client = _client([])
    starters = client.get("/api/starters").json()["starters"]
    assert any("weekly verbal call in Rev Intel" in item for item in starters)
    workspace = client.get("/api/workspace").json()
    assert workspace["assistant"]["name"] == "Stuart"
    groups = [group["label"] for group in workspace["tasks"]]
    assert groups == [
        "Forecasting",
        "Forecast inspection",
        "Rep participation",
        "Future quarter pipeline overview",
        "Manager policy & knowledge",
    ]
    faq = workspace["tasks"][-1]
    assert [item["id"] for item in faq["items"]] == ["manager_policy_faq"]
    assert faq["items"][0]["scopes"] == []
    assert any(
        item["id"] == "0068b00001Deal001"
        for item in workspace["filters"]["opps"]
    )
    assert any(
        item["id"] == "0068b00001Deal011"
        for item in workspace["filters"]["opps"]
    )
    report_ids = [item["id"] for item in workspace["filters"]["report_types"]]
    assert report_ids == ["this_quarter", "q_plus_1", "q_plus_2"]
    assert all("Geo:" not in item["label"] for item in workspace["filters"]["geos"])
    assert any(item.get("geos") for item in workspace["filters"]["boats"])
    assert all(
        group["agent"]
        in {
            "activity_engagement_specialist",
            "forecast_modeling_specialist",
            "rep_performance_specialist",
            "knowledge_base_rag",
        }
        for group in workspace["tasks"]
    )
    session = client.post("/api/session").json()
    assert session["session_id"]
    assert session["last_account"] == ""


def test_chat_streams_status_then_briefing_without_specialist_json() -> None:
    markdown = render_synthesis_markdown(
        SynthesisOutput(
            summary="NovaPay is high risk.",
            insights=["No economic buyer."],
            actions=[RecommendedAction(action="Call the CFO this week.")],
        )
    )
    client = _client(
        [
            _event("forecast_modeling_specialist", '{"status":"ok","secret":"do-not-show"}'),
            _event("forecast_modeling_specialist", '{"status":"ok"}'),
            _event("synthesis", '{"summary":"ignored"}'),
            _event("central_orchestrator", markdown),
        ]
    )
    created = client.post("/api/session").json()
    with client.stream(
        "POST",
        "/api/chat",
        json={"session_id": created["session_id"], "message": "Check the regional forecast for west."},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    events = _sse_events(body)
    types_seen = [event["type"] for event in events]
    assert types_seen[0] == "prompt"
    assert types_seen[1] == "status"
    assert types_seen[2] == "status"
    assert "delta" in types_seen
    reply = next(event for event in events if event["type"] == "reply")
    assert reply["kind"] == "briefing"
    assert reply["summary"] == "NovaPay is high risk."
    assert "forecast" in events[1]["label"].lower()
    assert events[2]["label"] == "Writing your briefing…"
    assert "".join(event["text"] for event in events if event["type"] == "delta")
    assert "do-not-show" not in body
    assert events[-1]["type"] == "done"


def test_chat_task_uses_selected_opportunity() -> None:
    from ui.catalog import FilterSelection, compose_task_message

    message = compose_task_message(
        _task_id("Sales Stage Validator"),
        FilterSelection(
            opps=["0068b00001Deal002"],
            geos=["east"],
            report_types=["q_plus_1"],
        ),
    )
    assert "Sales Stage Validator" in message
    assert "0068b00001Deal002" in message
    assert "Q+1" in message
    assert "Territory:" in message


def test_chat_task_endpoint_streams_composed_prompt() -> None:
    client = _client([_event("central_orchestrator", GREETING_REPLY)])
    created = client.post("/api/session").json()
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": created["session_id"],
            "task_id": _task_id("Sales Stage Validator"),
            "filters": {
                "opps": ["0068b00001Deal001"],
                "geos": [],
                "boats": [],
                "report_types": [],
            },
        },
    ) as response:
        body = "".join(response.iter_text())
    events = _sse_events(body)
    assert events[0]["type"] == "prompt"
    assert "Global Logistics Corp" in events[0]["text"]


def test_chat_rejects_empty_message() -> None:
    client = _client([])
    response = client.post("/api/chat", json={"session_id": "x", "message": "   "})
    assert response.status_code == 400


def test_chat_prefers_edited_message_over_task_id() -> None:
    client = _client([_event("central_orchestrator", GREETING_REPLY)])
    created = client.post("/api/session").json()
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": created["session_id"],
            "task_id": _task_id("Sales Stage Validator"),
            "message": "Review carve notes for 7-Eleven, and also check special terms.",
        },
    ) as response:
        body = "".join(response.iter_text())
    events = _sse_events(body)
    assert events[0]["type"] == "prompt"
    assert "special terms" in events[0]["text"]


def test_chat_accepts_csv_attachment() -> None:
    import base64

    client = _client([_event("central_orchestrator", GREETING_REPLY)])
    created = client.post("/api/session").json()
    payload = base64.b64encode(b"account,acv\nNovaPay,120000\n").decode("ascii")
    with client.stream(
        "POST",
        "/api/chat",
        json={
            "session_id": created["session_id"],
            "message": "Summarize this sheet for west.",
            "attachments": [
                {
                    "filename": "book.csv",
                    "mime_type": "text/csv",
                    "content_base64": payload,
                }
            ],
        },
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())
    events = _sse_events(body)
    assert events[0]["type"] == "prompt"
    assert "book.csv" in events[0]["text"]
