"""Usage: python -m src.agent <release_id> [event]

Plays the part of a GitHub event arriving (phase 11 will call this from a webhook). The model drives the tools.
Events: pull_request_opened (default), push, approved.
"""

import asyncio
import json
import sys
from dataclasses import asdict

from src.agent.agent import run_loop_with_server
from src.settings import get_settings


def main() -> None:
    if len(sys.argv) not in (2, 3):
        sys.exit(__doc__)
    get_settings()  # loads .env into the environment (keys are never printed)
    event = sys.argv[2] if len(sys.argv) == 3 else "pull_request_opened"
    run = asyncio.run(run_loop_with_server(sys.argv[1], event))
    print(json.dumps(asdict(run), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
