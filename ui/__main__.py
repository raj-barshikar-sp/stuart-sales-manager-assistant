"""Run the Sales Manager UI: python -m ui"""

from __future__ import annotations

import uvicorn

import agents.runtime_env  # noqa: F401 — dotenv + activity logger
from ui.app import app


def main() -> None:
    uvicorn.run(app, host="127.0.0.1", port=8080, log_level="info")


if __name__ == "__main__":
    main()
