# !/usr/bin/python
#
# Launch the actual contest jobs.

import asyncio

from absl import app

from flood.contest_orchestration import ContestOrchestrator
from flood.env import add_network_flag


def main(_: list[str]):
    orchestrator = ContestOrchestrator()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(orchestrator.run())
    finally:
        loop.close()


if __name__ == '__main__':
    add_network_flag(default='avalanche')
    app.run(main)
