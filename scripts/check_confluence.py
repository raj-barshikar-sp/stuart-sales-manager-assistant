"""Diagnose the Confluence FAQ connection without printing the token."""

from __future__ import annotations

import socket
import urllib.parse

from dotenv import load_dotenv

load_dotenv()

from agents.confluence_knowledge import (  # noqa: E402
    ConfluenceKnowledgeError,
    _request_json,
    confluence_config_from_env,
)

try:
    config = confluence_config_from_env()
except ConfluenceKnowledgeError as exc:
    raise SystemExit(f"config error: {exc}")

if config is None:
    raise SystemExit("Confluence is not configured in .env")

host = urllib.parse.urlparse(config.base_url).hostname or ""
print(f"base_url   {config.base_url}")
print(f"api_root   {config.api_root}")
print(f"email set  {bool(config.email)}")
print(f"token len  {len(config.api_token)}")
print(f"spaces     {', '.join(config.space_keys)}")

try:
    print(f"dns        {host} -> {socket.gethostbyname(host)}")
except OSError as exc:
    print(f"dns        FAILED for {host}: {exc}")

for label, path, params in (
    ("auth check", "/user/current", {}),
    ("space list", "/space", {"limit": 25}),
    ("cql search", "/content/search", {"cql": 'type=page', "limit": 1}),
):
    try:
        payload = _request_json(config, path, params)
    except ConfluenceKnowledgeError as exc:
        print(f"{label} FAILED: {exc}")
        continue
    if path == "/space":
        keys = [row.get("key") for row in payload.get("results") or []]
        print(f"{label} OK: readable spaces {keys}")
    elif path == "/user/current":
        print(f"{label} OK: {payload.get('displayName') or payload.get('accountId')}")
    else:
        print(f"{label} OK: {payload.get('size')} result(s)")
