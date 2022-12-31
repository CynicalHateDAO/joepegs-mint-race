import asyncio
import time
import traceback
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Callable, Any

from eth_typing import ChecksumAddress
from web3 import Web3
from web3.types import TxData

from deployment.contracts import flatlaunchpeg_abi
from flood.flood_waiting import watch_for_initialize_phases_async


@dataclass
class NamedContract(object):
    """Represents a contract we're interested in, and a user-friendly name."""
    name: str
    address: ChecksumAddress


class ContractInteractions(object):
    """Bookkeeping class for interactions with contracts in a block."""

    def __init__(self):
        self.addresses: dict[ChecksumAddress, int] = defaultdict(int)

    def add(self, address: ChecksumAddress):
        self.addresses[address] += 1

    def unique_addresses(self) -> int:
        return len([x for x, v in self.addresses.items() if v])

    def total_interactions(self) -> int:
        return sum(self.addresses.values())


class BlockMonitor(object):
    """Scan produced blocks and announces relevant data.

    Webhooks information about each block, including some stats related to
    how well we are flooding, plus how many interactions occurred with contracts
    that we are interested in.

    Additionally, supports announcing the first available block for minting.
    """

    def __init__(self, provider: Web3, monitored_contracts: list[NamedContract], hook_fn: Callable[[str], Any]):
        self.provider = provider
        self.monitored_contracts = monitored_contracts
        self.hook_fn = hook_fn
        self.scan_interval_seconds = .1

        # State updated during scanning.
        self.last_block_scanned = self.provider.eth.get_block_number()

        # Represents the clock time since last block; since block time is measured
        # in integers, it's not really that helpful.
        self.last_block_time = time.time()

        # Set during execution once we've seen the initializePhases event.
        self.start_time = 0

    async def start_scanning(self):
        # It might have been a while between creation and scanning start, so skip ahead
        # to the latest block and time.
        self.last_block_scanned = self.provider.eth.get_block_number()
        self.last_block_time = time.time()

        while True:
            try:
                await self.try_scan()
            except ValueError as ex:
                if 'unfinalized' in str(ex):
                    # This is an expected error, the next block is not available.
                    pass
                else:
                    print('Unexpected exception while scanning:', ex)
                    print(traceback.format_exc())
            except Exception as ex:
                print('Unexpected exception while scanning:', ex)
                print(traceback.format_exc())

            await asyncio.sleep(self.scan_interval_seconds)

    async def try_scan(self):
        # If this fails to return a block, the exception will break us out.
        block = self.provider.eth.get_block(self.last_block_scanned + 1, full_transactions=True)

        # Interesting per-block info.
        number = block['number']
        timestamp = block['timestamp']
        base_fee_gwei = int(Web3.fromWei(block['baseFeePerGas'], 'gwei'))
        gas_used_pct = block['gasUsed'] / block['gasLimit']
        count = len(block['transactions'])

        # Pick out interactions with the deployment we care about.
        interactions = {mc.address: ContractInteractions() for mc in self.monitored_contracts}
        block_tx: Sequence[TxData] = block['transactions']
        for tx in block_tx:
            try:
                to_address = Web3.toChecksumAddress(tx['to'])
                from_address = Web3.toChecksumAddress(tx['from'])
                if to_address in interactions:
                    interactions[to_address].add(from_address)
            except Exception as ex:
                # I have occasionally seen this pop up and I don't know why =(
                print('Unexpectedly failed to process a tx:', ex)
                print(tx)

        # Ensure we don't scan this block again.
        self.last_block_scanned = number

        # Build a message to hook to Discord / print to console.
        msg = f'Block:{number} TS:{timestamp} Fee:{base_fee_gwei:3d} GasUsed:{gas_used_pct:3.0%} Count:{count:3d}'

        # Manage the block time delta.
        prev_time = self.last_block_time
        self.last_block_time = time.time()
        delta_time = round(self.last_block_time - prev_time, 2)
        msg += f' Delta:{delta_time}'

        # A bit hacky, but if we externally detected the allowlist start time and set it
        # into the monitor, then we'll inject this alert into the webhook to make it easier
        # to identify if we're successfully flooding past the start block.
        if self.start_time and self.start_time < timestamp:
            msg += '\n===== ALLOWLIST START BLOCK ====='
            self.start_time = 0

        # Include details about all the contracts we're interested in.
        for mc in self.monitored_contracts:
            item = interactions[mc.address]
            msg += f'\n\t{mc.name} : {item.total_interactions():2d} from {item.unique_addresses():2d}'

        await self.hook_fn(msg)

    async def announce_init(self):
        """Task that waits for initPhases and announces that we saw it.

        We don't want the spammers/minters to do this alert since they'll be busy.
        """
        target_address = [x for x in self.monitored_contracts if 'target' in x.name.lower()][0].address
        contract = self.provider.eth.contract(address=target_address, abi=flatlaunchpeg_abi())
        start_time = await watch_for_initialize_phases_async(contract)
        await self.hook_fn(f'Initialize triggered with start_time {start_time}')
