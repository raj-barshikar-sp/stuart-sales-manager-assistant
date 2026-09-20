"""Read a JSON object that is still being streamed.

Only values that have fully arrived are returned, so callers can render a
growing preview without ever showing a half-written string or object.
"""

from __future__ import annotations

import json
from typing import Any

_WHITESPACE = " \t\r\n"
_LITERAL_END = ",]} \t\r\n"


class _Incomplete(Exception):
    """Raised when the text ends in the middle of a value."""


def _skip_ws(text: str, index: int) -> int:
    while index < len(text) and text[index] in _WHITESPACE:
        index += 1
    return index


def _scan_string(text: str, index: int) -> tuple[str, int]:
    cursor = index + 1
    while cursor < len(text):
        char = text[cursor]
        if char == "\\":
            if text[cursor + 1 : cursor + 2] == "u":
                if cursor + 6 > len(text):
                    raise _Incomplete
                cursor += 6
                continue
            if cursor + 2 > len(text):
                raise _Incomplete
            cursor += 2
            continue
        if char == '"':
            return json.loads(text[index : cursor + 1]), cursor + 1
        cursor += 1
    raise _Incomplete


def _scan_array(text: str, index: int, sink: list[Any] | None = None) -> tuple[list[Any], int]:
    items: list[Any] = []
    cursor = _skip_ws(text, index + 1)
    if cursor < len(text) and text[cursor] == "]":
        return items, cursor + 1
    while True:
        value, cursor = _scan_value(text, cursor)
        items.append(value)
        if sink is not None:
            sink.append(value)
        cursor = _skip_ws(text, cursor)
        if cursor >= len(text):
            raise _Incomplete
        if text[cursor] == ",":
            cursor = _skip_ws(text, cursor + 1)
            continue
        if text[cursor] == "]":
            return items, cursor + 1
        raise _Incomplete


def _scan_object(text: str, index: int) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    cursor = _skip_ws(text, index + 1)
    if cursor < len(text) and text[cursor] == "}":
        return result, cursor + 1
    while True:
        if cursor >= len(text) or text[cursor] != '"':
            raise _Incomplete
        key, cursor = _scan_string(text, cursor)
        cursor = _skip_ws(text, cursor)
        if cursor >= len(text) or text[cursor] != ":":
            raise _Incomplete
        value, cursor = _scan_value(text, _skip_ws(text, cursor + 1))
        result[key] = value
        cursor = _skip_ws(text, cursor)
        if cursor >= len(text):
            raise _Incomplete
        if text[cursor] == ",":
            cursor = _skip_ws(text, cursor + 1)
            continue
        if text[cursor] == "}":
            return result, cursor + 1
        raise _Incomplete


def _scan_value(text: str, index: int) -> tuple[Any, int]:
    index = _skip_ws(text, index)
    if index >= len(text):
        raise _Incomplete
    char = text[index]
    if char == '"':
        return _scan_string(text, index)
    if char == "{":
        return _scan_object(text, index)
    if char == "[":
        return _scan_array(text, index)
    cursor = index
    while cursor < len(text) and text[cursor] not in _LITERAL_END:
        cursor += 1
    if cursor >= len(text):
        raise _Incomplete
    try:
        return json.loads(text[index:cursor]), cursor
    except json.JSONDecodeError as exc:
        raise _Incomplete from exc


def completed_fields(text: str) -> dict[str, Any]:
    """Return the top-level keys of `text` whose values have fully arrived.

    A top-level array is truncated to the elements that finished, so a list
    grows one complete item at a time as more text streams in.
    """
    index = _skip_ws(text, 0)
    if index >= len(text) or text[index] != "{":
        return {}
    result: dict[str, Any] = {}
    cursor = _skip_ws(text, index + 1)
    while True:
        if cursor >= len(text) or text[cursor] != '"':
            return result
        try:
            key, cursor = _scan_string(text, cursor)
        except _Incomplete:
            return result
        cursor = _skip_ws(text, cursor)
        if cursor >= len(text) or text[cursor] != ":":
            return result
        cursor = _skip_ws(text, cursor + 1)
        if cursor < len(text) and text[cursor] == "[":
            sink: list[Any] = []
            try:
                value, cursor = _scan_array(text, cursor, sink)
            except _Incomplete:
                if sink:
                    result[key] = sink
                return result
            result[key] = value
        else:
            try:
                value, cursor = _scan_value(text, cursor)
            except _Incomplete:
                return result
            result[key] = value
        cursor = _skip_ws(text, cursor)
        if cursor < len(text) and text[cursor] == ",":
            cursor = _skip_ws(text, cursor + 1)
            continue
        return result
