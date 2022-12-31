import asyncio

from client.fast_client import FastContractClient


class NoiseGenerator(object):
    """Utility to asynchronously spam some simple transactions.

    Fuji has very few ambient TX, and local has none. This utility can
    be used to generate a steady stream of transactions while tests are
    running to make sure block production is constant.
    """

    def __init__(self, client: FastContractClient, sleep_time_sec: float):
        self.client = client
        self.sleep_time_sec = sleep_time_sec

    async def start_noise(self):
        while True:
            self.client.send_contract_tx('consume', [self.client.max_priority_fee_gwei])
            await asyncio.sleep(self.sleep_time_sec)
