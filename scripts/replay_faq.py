"""Replay manager questions against a running UI and print the final answer."""

from __future__ import annotations

import json
import sys
import time

import httpx

QUESTIONS = sys.argv[1:] or [
    "Who approves a 22% discount on ISC?",
    "tell me about deal stages?",
    "In detail explain SS20 stage of deal",
]


def ask(client: httpx.Client, session_id: str, message: str) -> None:
    started = time.perf_counter()
    text = ""
    statuses: list[str] = []
    first = 0.0
    with client.stream(
        "POST",
        "http://127.0.0.1:8080/api/chat",
        json={"message": message, "session_id": session_id},
        timeout=120,
    ) as response:
        for line in response.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            if event.get("type") == "status":
                statuses.append(event["label"])
            if event.get("type") == "delta":
                first = first or time.perf_counter() - started
                text += event["text"]
            if event.get("type") == "reset":
                text = ""
            if event.get("type") == "reply":
                text = event.get("markdown") or event.get("text") or text
    print("=" * 78)
    print(f"Q: {message}")
    print(f"   first token {first:.1f}s | total {time.perf_counter() - started:.1f}s")
    print(f"   statuses: {statuses}")
    print(f"   chars: {len(text)}")
    print("-" * 78)
    print(text.strip())


with httpx.Client() as client:
    session_id = client.post("http://127.0.0.1:8080/api/session").json()["session_id"]
    for question in QUESTIONS:
        ask(client, session_id, question)
