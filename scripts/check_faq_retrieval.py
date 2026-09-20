"""Exercise live FAQ retrieval end to end against Confluence."""

from __future__ import annotations

import sys
import time

from dotenv import load_dotenv

load_dotenv()

from agents.faq_knowledge import (  # noqa: E402
    load_knowledge_sections,
    search_faq_documents,
)

started = time.perf_counter()
sections = load_knowledge_sections()
print(f"indexed sections: {len(sections)} in {time.perf_counter() - started:.1f}s")
if sections:
    pages = {row["document_id"] for row in sections}
    spaces = {row.get("space_key", "") for row in sections}
    print(f"pages: {len(pages)} | spaces: {sorted(spaces)}")

questions = sys.argv[1:] or [
    "How is account ownership determined when the HQ is in another territory?",
    "Who approves a 22% discount?",
]
for question in questions:
    hits = search_faq_documents(question)
    print(f"\nQ: {question}")
    if not hits:
        print("  no matching sections")
        continue
    for row in hits[:3]:
        print(f"  - {row['title']} § {row['section']} ({len(row['content'])} chars)")
