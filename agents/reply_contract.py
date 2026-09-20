"""Shared manager-facing reply shape injected into every specialist."""

REPLY_CONTRACT = """
Reply contract (every specialist uses this shape after tools run):
Return the structured specialist schema. Do not chat. Do not invent numbers.
Leave findings empty when records tell the full story. Synthesis writes the
manager brief from verified records.
Never name tools, files, CSV/JSON tables, or other agents in customer-facing copy_ready lines.
""".strip()
