# !/usr/bin/python
#
# This script runs a full integration test against fuji or local avalanche.
# It requires the .env_<network> to be fully configured.

import asyncio

from absl import app, flags

from flood.env import Config, add_network_flag
from flood.flood_configs import FloodGasSettings
from setup.orchestration import TestOrchestrator


def main(_: list[str]):
    gas_settings = FloodGasSettings(gas_tip_gwei=flags.FLAGS.gas_tip)
    orchestrator = TestOrchestrator(Config.from_flag(), flags.FLAGS.duration, gas_settings)
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(orchestrator.run())
    finally:
        loop.close()


if __name__ == '__main__':
    add_network_flag(default='local')
    flags.DEFINE_integer('gas_tip', 10, 'Value to use for the gas tip, in gwei')
    flags.DEFINE_integer('duration', 6, 'Amount of time between initializePhases and allowlist start, in seconds')
    app.run(main)
