"""Search Confluence text to locate policy pages and the spaces holding them."""

from __future__ import annotations

import sys

from dotenv import load_dotenv

load_dotenv()

from agents.confluence_knowledge import (  # noqa: E402
    _request_json,
    confluence_config_from_env,
)

config = confluence_config_from_env()
if config is None:
    raise SystemExit("Confluence is not configured in .env")

phrase = " ".join(sys.argv[1:]) or "discount approval matrix"
allowed = set(config.space_keys)

for scope, cql in (
    (
        "allowlisted spaces",
        f'type=page AND space in ({", ".join(chr(34) + k + chr(34) for k in allowed)})'
        f' AND text ~ "{phrase}"',
    ),
    ("entire site", f'type=page AND text ~ "{phrase}"'),
):
    print(f"\n=== {scope}: text ~ \"{phrase}\" ===")
    try:
        payload = _request_json(
            config,
            "/content/search",
            {"cql": cql, "expand": "space", "limit": 15},
        )
    except Exception as exc:  # noqa: BLE001 - diagnostic output
        print(f"  failed: {exc}")
        continue
    rows = payload.get("results") or []
    if not rows:
        print("  no matches")
        continue
    for row in rows:
        space = str((row.get("space") or {}).get("key") or "?")
        marker = "" if space in allowed else "   <-- OUTSIDE ALLOWLIST"
        print(f"  [{space:12}] {row.get('title')}{marker}")
