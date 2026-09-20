"""FastAPI app that streams the orchestrator to the Sales Manager UI."""

from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.events import Event
from google.adk.sessions import InMemorySessionService
from google.genai import types
from pydantic import BaseModel, Field

from agents.activity import log_activity, logger, preview

from ui.attachments import decode_attachments, prompt_and_inline
from ui.briefing import parse_reply
from ui.catalog import (
    FilterSelection,
    apply_filter_notes,
    compose_task_message,
    default_starters,
    workspace_catalog,
)
from ui.progress import status_for_author
from ui.stream import word_deltas

APP_NAME = "orchestrator"
STATIC_DIR = Path(__file__).with_name("static")
SESSION_KEYS = ("ae_name", "last_account", "last_territory", "last_opportunity")


class ChatFilters(BaseModel):
    geos: list[str] = Field(default_factory=list)
    boats: list[str] = Field(default_factory=list)
    opps: list[str] = Field(default_factory=list)
    report_types: list[str] = Field(default_factory=list)


class ChatAttachment(BaseModel):
    filename: str = ""
    mime_type: str = ""
    content_base64: str = ""


class ChatRequest(BaseModel):
    message: str = ""
    session_id: str = ""
    task_id: str = ""
    filters: ChatFilters | None = None
    attachments: list[ChatAttachment] = Field(default_factory=list)


def _event_text(event: Event) -> str:
    if not event.content or not event.content.parts:
        return ""
    return "\n".join(
        part.text for part in event.content.parts if getattr(part, "text", None)
    )


def _sse(payload: dict[str, Any]) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _context_from_state(state: Any) -> dict[str, str]:
    return {key: str(state.get(key) or "") for key in SESSION_KEYS}


def create_app(
    *,
    runner: Any | None = None,
    session_service: InMemorySessionService | None = None,
) -> FastAPI:
    """Build the UI app. Tests inject a fake runner so Gemini is not required."""

    sessions = session_service or InMemorySessionService()
    live_runner = runner
    app = FastAPI(title="Stuart", docs_url=None, redoc_url=None)

    def _runner() -> Any:
        nonlocal live_runner
        if live_runner is None:
            import agents.runtime_env  # noqa: F401

            from google.adk.runners import Runner

            from agents.orchestrator.agent import root_agent

            live_runner = Runner(
                agent=root_agent,
                app_name=APP_NAME,
                session_service=sessions,
            )
        return live_runner

    async def _ensure_session(session_id: str) -> str:
        sid = session_id.strip() or str(uuid.uuid4())
        existing = await sessions.get_session(
            app_name=APP_NAME, user_id="ae", session_id=sid
        )
        if existing is None:
            created = await sessions.create_session(
                app_name=APP_NAME, user_id="ae", session_id=sid
            )
            log_activity("session.create", session_id=created.id)
            return created.id
        return existing.id

    @app.get("/api/starters")
    async def starters() -> dict[str, list[str]]:
        return {"starters": default_starters()}

    @app.get("/api/workspace")
    async def workspace() -> dict:
        return workspace_catalog()

    @app.post("/api/session")
    async def new_session() -> dict[str, str]:
        session = await sessions.create_session(app_name=APP_NAME, user_id="ae")
        log_activity("session.create", session_id=session.id)
        return {"session_id": session.id, **_context_from_state(session.state)}

    @app.get("/api/session/{session_id}")
    async def read_session(session_id: str) -> dict[str, str]:
        session = await sessions.get_session(
            app_name=APP_NAME, user_id="ae", session_id=session_id
        )
        if session is None:
            raise HTTPException(status_code=404, detail="Unknown session")
        return {"session_id": session.id, **_context_from_state(session.state)}

    async def _chat_stream(
        session_id: str,
        message: str,
        *,
        visible: str,
        inline: list | None = None,
    ) -> AsyncIterator[str]:
        seen_status: set[str] = set()
        final_text = ""
        emitted = ""
        log_activity(
            "chat.start",
            session_id=session_id,
            query=preview(message),
            attachments=len(inline or []),
        )
        yield _sse({"type": "prompt", "text": visible})
        parts = [types.Part.from_text(text=message)]
        for item in inline or []:
            parts.append(
                types.Part.from_bytes(data=item.data, mime_type=item.mime_type)
            )
        try:
            async for event in _runner().run_async(
                user_id="ae",
                session_id=session_id,
                new_message=types.Content(
                    role="user",
                    parts=parts,
                ),
                run_config=RunConfig(streaming_mode=StreamingMode.SSE),
            ):
                author = event.author or ""
                label = status_for_author(author)
                if label and label not in seen_status:
                    seen_status.add(label)
                    yield _sse({"type": "status", "label": label})
                text = _event_text(event)
                if author != "central_orchestrator" or not text.strip():
                    continue
                if text.startswith(emitted):
                    addition = text[len(emitted) :]
                else:
                    # The final answer diverged from the draft; restart the pane.
                    yield _sse({"type": "reset"})
                    addition = text
                final_text = text
                emitted = text
                for chunk in word_deltas(addition):
                    yield _sse({"type": "delta", "text": chunk})
        except Exception as exc:
            logger.exception("chat.failed session_id=%s", session_id)
            log_activity(
                "chat.failed",
                session_id=session_id,
                error=type(exc).__name__,
            )
            yield _sse(
                {
                    "type": "error",
                    "message": "I couldn't complete that request. Try again.",
                    "detail": type(exc).__name__,
                }
            )
            return

        if final_text:
            yield _sse({"type": "reply", **parse_reply(final_text)})
            log_activity(
                "chat.done",
                session_id=session_id,
                chars=len(final_text),
                statuses=sorted(seen_status),
            )
        else:
            log_activity("chat.empty", session_id=session_id)
            yield _sse(
                {
                    "type": "error",
                    "message": "I didn't get a briefing back. Try that again.",
                }
            )

        session = await sessions.get_session(
            app_name=APP_NAME, user_id="ae", session_id=session_id
        )
        if session is not None:
            yield _sse({"type": "context", **_context_from_state(session.state)})
        yield _sse({"type": "done"})

    @app.post("/api/chat")
    async def chat(body: ChatRequest) -> StreamingResponse:
        message = body.message.strip()
        selection = FilterSelection()
        if body.filters is not None:
            selection = FilterSelection(
                geos=body.filters.geos,
                boats=body.filters.boats,
                opps=body.filters.opps,
                report_types=body.filters.report_types,
            )
        decoded = decode_attachments(
            [item.model_dump() for item in body.attachments]
        )
        if body.task_id and not message:
            try:
                message = compose_task_message(body.task_id, selection)
            except KeyError as exc:
                log_activity("chat.unknown_task", task_id=body.task_id)
                raise HTTPException(status_code=400, detail="Unknown task") from exc
        elif message:
            if "Working filters:" not in message:
                message = apply_filter_notes(message, selection)
        elif decoded:
            message = "Review the attached files."
        else:
            raise HTTPException(status_code=400, detail="Message is empty")
        filenames = [item.filename for item in decoded]
        visible = message
        if filenames and "Attached" not in visible:
            visible = message.rstrip() + "\n\nAttached: " + ", ".join(filenames)
        message, inline = prompt_and_inline(message, decoded)
        session_id = await _ensure_session(body.session_id)
        log_activity(
            "chat.request",
            session_id=session_id,
            task_id=body.task_id or "",
            query=preview(message),
            geos=selection.geos,
            reps=selection.boats,
            opps=selection.opps,
            horizon=selection.report_types,
            attachments=len(decoded),
        )
        return StreamingResponse(
            _chat_stream(session_id, message, visible=visible, inline=inline),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "X-Session-Id": session_id,
            },
        )

    @app.get("/")
    async def home() -> Any:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/app")
    async def workspace_page() -> Any:
        return RedirectResponse("/", status_code=302)

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app


app = create_app()
