"""List readable global spaces so CONFLUENCE_SPACE_KEYS can be set correctly."""

from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from agents.confluence_knowledge import (  # noqa: E402
    _cql,
    _request_json,
    confluence_config_from_env,
)

config = confluence_config_from_env()
if config is None:
    raise SystemExit("Confluence is not configured in .env")

spaces: list[tuple[str, str]] = []
start = 0
while True:
    payload = _request_json(
        config, "/space", {"type": "global", "limit": 100, "start": start}
    )
    rows = payload.get("results") or []
    spaces.extend((str(row.get("key")), str(row.get("name"))) for row in rows)
    if len(rows) < 100:
        break
    start += len(rows)

print(f"readable global spaces: {len(spaces)}")
for key, name in sorted(spaces):
    print(f"  {key:24} {name}")

configured = set(config.space_keys)
missing = sorted(configured - {key for key, _ in spaces})
print(f"\nconfigured: {sorted(configured)}")
print(f"missing   : {missing or 'none'}")

try:
    result = _request_json(config, "/content/search", {"cql": _cql(config), "limit": 1})
    print(f"pages matching configured CQL: {result.get('size')}")
except Exception as exc:  # noqa: BLE001 - diagnostic output
    print(f"configured CQL failed: {exc}")
