"""Section-level knowledge loader for allowlisted Confluence spaces."""

from __future__ import annotations

import base64
import json
import os
import re
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from functools import lru_cache
from dataclasses import dataclass
from html.parser import HTMLParser
from typing import Any

from agents.activity import log_activity

_SAFE_KEY = re.compile(r"^[A-Za-z0-9_-]+$")
_BLOCK_TAGS = {"p", "div", "li", "tr", "br", "blockquote", "pre"}


class ConfluenceKnowledgeError(RuntimeError):
    """Raised when configured Confluence knowledge cannot be loaded."""


@dataclass(frozen=True)
class ConfluenceConfig:
    base_url: str
    api_token: str
    space_keys: tuple[str, ...]
    email: str = ""
    labels: tuple[str, ...] = ()
    timeout_seconds: float = 15.0
    cache_ttl_seconds: float = 300.0
    page_limit: int = 100
    max_pages: int = 1000

    @property
    def api_root(self) -> str:
        """Confluence v1 REST root; v2 has no CQL `/content/search` equivalent."""
        base = self.base_url.rstrip("/")
        if base.endswith("/rest/api"):
            return base
        # Atlassian Cloud always serves Confluence under the /wiki context path.
        parsed = urllib.parse.urlparse(base)
        if parsed.hostname and parsed.hostname.endswith(".atlassian.net"):
            if not parsed.path.strip("/").startswith("wiki"):
                base = f"{base}/wiki"
        return f"{base}/rest/api"

    @property
    def authorization(self) -> str:
        if self.email:
            raw = f"{self.email}:{self.api_token}".encode()
            return f"Basic {base64.b64encode(raw).decode()}"
        return f"Bearer {self.api_token}"


def _csv(name: str) -> tuple[str, ...]:
    return tuple(
        value.strip()
        for value in os.getenv(name, "").split(",")
        if value.strip()
    )


def confluence_config_from_env() -> ConfluenceConfig | None:
    """Build config only when Confluence is fully configured.

    An allowlist is mandatory: the FAQ agent must never search every space the
    service account happens to be able to read.
    """
    base_url = os.getenv("CONFLUENCE_BASE_URL", "").strip()
    api_token = os.getenv("CONFLUENCE_API_TOKEN", "").strip()
    space_keys = _csv("CONFLUENCE_SPACE_KEYS")
    if not any((base_url, api_token, space_keys)):
        return None
    missing = [
        name
        for name, value in (
            ("CONFLUENCE_BASE_URL", base_url),
            ("CONFLUENCE_API_TOKEN", api_token),
            ("CONFLUENCE_SPACE_KEYS", space_keys),
        )
        if not value
    ]
    if missing:
        raise ConfluenceKnowledgeError(
            f"Incomplete Confluence configuration: missing {', '.join(missing)}"
        )
    unsafe = [key for key in (*space_keys, *_csv("CONFLUENCE_LABELS")) if not _SAFE_KEY.fullmatch(key)]
    if unsafe:
        raise ConfluenceKnowledgeError("Confluence space keys and labels contain invalid characters")
    return ConfluenceConfig(
        base_url=base_url,
        api_token=api_token,
        email=os.getenv("CONFLUENCE_EMAIL", "").strip(),
        space_keys=space_keys,
        labels=_csv("CONFLUENCE_LABELS"),
        timeout_seconds=float(os.getenv("CONFLUENCE_TIMEOUT_SECONDS", "15")),
        cache_ttl_seconds=float(os.getenv("CONFLUENCE_CACHE_TTL_SECONDS", "300")),
        page_limit=max(1, min(100, int(os.getenv("CONFLUENCE_PAGE_LIMIT", "100")))),
        max_pages=max(1, int(os.getenv("CONFLUENCE_MAX_PAGES", "1000"))),
    )


class _StorageTextParser(HTMLParser):
    """Convert Confluence storage HTML to heading-aware plain text."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.lines: list[str] = []
        self._buffer: list[str] = []
        self._heading_level = 0
        self._skip_depth = 0

    def _flush(self) -> None:
        text = " ".join("".join(self._buffer).split())
        self._buffer = []
        if text:
            prefix = f"{'#' * self._heading_level} " if self._heading_level else ""
            self.lines.append(f"{prefix}{text}")
        self._heading_level = 0

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        tag = tag.lower()
        if tag in {"script", "style"}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag in _BLOCK_TAGS or re.fullmatch(r"h[1-4]", tag):
            self._flush()
        if re.fullmatch(r"h[1-4]", tag):
            self._heading_level = int(tag[1])
        if tag == "li":
            self._buffer.append("- ")

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style"} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in _BLOCK_TAGS or re.fullmatch(r"h[1-4]", tag):
            self._flush()

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self._buffer.append(data)

    def finish(self) -> str:
        self._flush()
        return "\n".join(self.lines)


def _storage_to_sections(storage: str) -> list[tuple[str, str]]:
    parser = _StorageTextParser()
    parser.feed(storage)
    body = parser.finish()
    chunks: list[tuple[str, str]] = []
    path: list[str] = []
    heading = "Overview"
    lines: list[str] = []

    def flush() -> None:
        content = "\n".join(lines).strip()
        if content:
            chunks.append((heading, content))

    for line in body.splitlines():
        match = re.match(r"^(#{1,4})\s+(.+)$", line)
        if not match:
            lines.append(line)
            continue
        flush()
        level = len(match.group(1))
        path[level - 1 :] = [match.group(2).strip()]
        heading = " > ".join(path)
        lines = []
    flush()
    return chunks


@lru_cache(maxsize=1)
def _ssl_context() -> ssl.SSLContext:
    """Verify TLS against certifi, since a python.org install may ship no CA file.

    Set CONFLUENCE_CA_BUNDLE when a corporate proxy re-signs traffic.
    """
    ca_bundle = os.getenv("CONFLUENCE_CA_BUNDLE", "").strip()
    if not ca_bundle:
        try:
            import certifi

            ca_bundle = certifi.where()
        except ModuleNotFoundError:
            ca_bundle = ""
    return ssl.create_default_context(cafile=ca_bundle or None)


def _request_json(
    config: ConfluenceConfig, path: str, params: dict[str, Any]
) -> dict[str, Any]:
    return _request_url(
        config, f"{config.api_root}{path}?{urllib.parse.urlencode(params)}"
    )


def _request_url(config: ConfluenceConfig, url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "Authorization": config.authorization,
            "User-Agent": "Project-Gru-Sales-Manager/1.0",
        },
    )
    try:
        with urllib.request.urlopen(
            request, timeout=config.timeout_seconds, context=_ssl_context()
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        hint = {
            401: "check CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN",
            403: "the account cannot read the allowlisted spaces",
            404: "check CONFLUENCE_BASE_URL ends with the site's wiki path",
        }.get(exc.code, "")
        raise ConfluenceKnowledgeError(
            f"Confluence returned HTTP {exc.code} for {config.api_root}"
            + (f" — {hint}" if hint else "")
        ) from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        # URLError alone hides DNS/TLS/proxy causes, so name the underlying reason.
        reason = getattr(exc, "reason", exc)
        raise ConfluenceKnowledgeError(
            f"Could not reach {config.api_root}: {type(exc).__name__}: {reason}"
        ) from exc
    if not isinstance(payload, dict):
        raise ConfluenceKnowledgeError("Confluence returned an invalid response")
    return payload


def _cql(config: ConfluenceConfig) -> str:
    spaces = ", ".join(f'"{key}"' for key in config.space_keys)
    clauses = [f"type=page", f"space in ({spaces})"]
    if config.labels:
        labels = ", ".join(f'"{label}"' for label in config.labels)
        clauses.append(f"label in ({labels})")
    return " AND ".join(clauses)


def _page_url(config: ConfluenceConfig, links: dict[str, Any]) -> str:
    base = str(links.get("base") or config.base_url).rstrip("/")
    target = str(links.get("webui") or links.get("self") or "")
    if target.startswith(("http://", "https://")):
        return target
    return f"{base}/{target.lstrip('/')}"


def _next_url(config: ConfluenceConfig, payload: dict[str, Any]) -> str:
    """Resolve the cursor link for the next batch, or return "" when the page is last."""
    links = payload.get("_links") or {}
    target = str(links.get("next") or "")
    if not target:
        return ""
    if target.startswith(("http://", "https://")):
        return target
    # `base` carries the site's context path (`/wiki` on Cloud) that `next` omits.
    base = str(links.get("base") or config.base_url).rstrip("/")
    return f"{base}/{target.lstrip('/')}"


def fetch_confluence_sections(config: ConfluenceConfig) -> tuple[dict[str, Any], ...]:
    """Fetch current pages and split each page into independently searchable sections."""
    pages: list[dict[str, Any]] = []
    # CQL search can repeat rows across pages, so identity is the page id.
    seen_ids: set[str] = set()
    url = f"{config.api_root}/content/search?" + urllib.parse.urlencode(
        {
            "cql": _cql(config),
            "expand": "body.storage,version,space",
            "limit": config.page_limit,
        }
    )
    while url and len(pages) < config.max_pages:
        payload = _request_url(config, url)
        batch = payload.get("results") or []
        if not isinstance(batch, list):
            raise ConfluenceKnowledgeError("Confluence search results were invalid")
        for row in batch:
            if not isinstance(row, dict) or len(pages) >= config.max_pages:
                continue
            page_id = str(row.get("id") or "")
            if page_id and page_id in seen_ids:
                continue
            seen_ids.add(page_id)
            pages.append(row)
        # Cloud paginates this endpoint by opaque cursor; `start` offsets silently
        # replay the first batch, so the next link is the only reliable way forward.
        url = _next_url(config, payload)

    records: list[dict[str, Any]] = []
    for page in pages:
        page_id = str(page.get("id") or "")
        title = str(page.get("title") or "Untitled Confluence page")
        storage = str(
            (((page.get("body") or {}).get("storage") or {}).get("value")) or ""
        )
        links = page.get("_links") or {}
        source = _page_url(config, links)
        updated = str(((page.get("version") or {}).get("when")) or "")
        for section, content in _storage_to_sections(storage):
            records.append(
                {
                    "document_id": page_id,
                    "title": title,
                    "section": section,
                    "content": content,
                    "last_updated": updated,
                    "effective_fiscal_year": "",
                    "source": source,
                    "space_key": str(((page.get("space") or {}).get("key")) or ""),
                }
            )
    log_activity(
        "confluence.loaded",
        spaces=list(config.space_keys),
        pages=len(pages),
        sections=len(records),
    )
    return tuple(records)


_CACHE_LOCK = threading.Lock()
_CACHE_KEY: tuple[Any, ...] = ()
_CACHE_UNTIL = 0.0
_CACHE_SECTIONS: tuple[dict[str, Any], ...] = ()


def load_confluence_sections(
    config: ConfluenceConfig | None = None, *, force: bool = False
) -> tuple[dict[str, Any], ...]:
    """Return a bounded in-memory index, refreshing after the configured TTL."""
    global _CACHE_KEY, _CACHE_SECTIONS, _CACHE_UNTIL
    config = config or confluence_config_from_env()
    if config is None:
        return ()
    key = (
        config.base_url,
        config.email,
        config.space_keys,
        config.labels,
        config.max_pages,
    )
    now = time.monotonic()
    with _CACHE_LOCK:
        if not force and key == _CACHE_KEY and now < _CACHE_UNTIL:
            return _CACHE_SECTIONS
        sections = fetch_confluence_sections(config)
        _CACHE_KEY = key
        _CACHE_SECTIONS = sections
        _CACHE_UNTIL = now + config.cache_ttl_seconds
        return sections
