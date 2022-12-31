import asyncio
import random
import time
import traceback
from asyncio import Task

from eth_typing import ChecksumAddress
from web3 import Web3

from accounts.users import UserLoader
from client.endpoints import make_avax_provider
from client.fast_client import FastContractClient
from deployment.contracts import flatlaunchpeg_abi, allowlist_proxy_abi
from flood.discord import hook_it_async
from flood.env import Config
from flood.flood_configs import FloodGasSettings
from flood.flood_waiting import watch_for_initialize_phases_async
from launcher.gcb_mint_launcher import GcbLauncher
from launcher.mint_launcher import Launcher
from setup.block_monitor import BlockMonitor, NamedContract


class ContestOrchestrator(object):
    """Starts the tasks in mint contest mode.

    To ensure I can't fuck anything up at last minute, most things are hardcoded.
    """

    def __init__(self):
        self.config = Config(network='avalanche')

        self.test_name = f'CONTEST MODE'
        self.gas_settings = FloodGasSettings()
        self.mint_contract = Web3.toChecksumAddress('0x0A50EE15688665C4bB98c802F5ee11fEc3DF0B80')

        self.w3 = make_avax_provider(self.config.provider_uris[0])

        self.deployer = UserLoader.deployer()
        self.minters = UserLoader.minters()
        self.proxyminters = UserLoader.proxy_minters()
        self.spammers = UserLoader.spammers()

        # Contains the contracts we deploy to proxy-mint the launchpeg.
        self.deployed_proxies: list[ChecksumAddress] = [
            Web3.toChecksumAddress('0x3bF6f6442e1eA7c6320a71C785355de936d0b3B7'),
            Web3.toChecksumAddress('0x9C3cF6F1Cfe83d9Cb0E43e3B97A5ABE0AEc66e1c'),
            Web3.toChecksumAddress('0x407961f3EaA2ffCAF621347887931b57d30A309B'),
        ]

        # Async jobs we start should get stuck in here so that we can cleanly
        # shut them down at the end (or we get annoying warnings).
        self.tasks: list[Task] = []

        # Jobs use different amounts of gas, shuffle the ordering a bit to make it less
        # likely for specific accounts to run out.
        random.shuffle(self.spammers)

    async def hook(self, msg: str):
        """Sends a discord webhook as the orchestrator."""
        await hook_it_async(self.config.orchestrator_hook, msg)

    async def run(self):
        """Run in contest mode, catching errors and alerting on them."""
        try:
            await self._run()
        except Exception as ex:
            print(traceback.format_exc())
            await self.hook('Test failed: ' + str(ex))

    async def _run(self):
        await self.hook(f'Starting up {self.test_name}')

        # Before we start, make sure we have enough avax in each account.
        # Also store the amount of avax across all accounts so we can later compute
        # how much this cost us.
        starting_balance = await self.check_balances()

        # Capture the total nonce value so we can later determine how many tx were sent.
        starting_nonce_total = await self.compute_nonce_total()

        # The client we'll use to operate on the new launchpeg.
        mint_client = FastContractClient([self.w3], self.deployer.account,
                                         self.mint_contract, flatlaunchpeg_abi())

        # Double check that didn't screw up.
        await self.verify_allowlist(mint_client)

        # For mainnet/testnet tests, we start tasks on GCB.
        job_sleep_time = 100
        job_launcher = GcbLauncher(self.mint_contract, self.config.network, self.gas_settings)

        # Actually start all the jobs.
        await self.start_jobs(job_launcher)

        # The cloud build jobs in particular take a long time to start up.
        await asyncio.sleep(job_sleep_time)

        # Check that all the jobs are running, and alert if not.
        await self.verify_jobs(job_launcher)

        # Start up the monitor function.
        monitor = await self.start_monitor(self.mint_contract)

        # Give things a few seconds to stabilize.
        await asyncio.sleep(5)

        # Start watching for the initialize phases call.
        start_time = await watch_for_initialize_phases_async(mint_client.contract)

        # Update the monitor so that it knows when to announce the first mint block.
        monitor.start_time = start_time

        # Sleep until the mint time, then do an announcement about the mint starting.
        # Should line up roughly with the block-level announcement.
        await asyncio.sleep(start_time - time.time())
        await self.hook(f'Start time {start_time} reached; mint should occur after this')

        # Sleep a bit more to ensure that the spam ended and minting process completed.
        await asyncio.sleep(60)

        # Clean shutdown for the various started tasks.
        for task in self.tasks:
            task.cancel()

        # Check to see if any jobs are still running, they might need to get cleaned up.
        await self.verify_jobs(job_launcher)

        # Figure out how much we spent on this test.
        ending_balance = await self.check_balances()
        consumed = round(Web3.fromWei(starting_balance - ending_balance, 'ether'), 2)

        # Capture the final nonce total and announce the delta.
        final_nonce_total = await self.compute_nonce_total()
        tx_sent = final_nonce_total - starting_nonce_total

        await self.hook(f'Finished running test, {consumed} AVAX consumed in {tx_sent} transactions')

        # For the proxy minter, presumably we got some nfts. Test extracting them
        # back to the deployer wallet.
        await self.recover_tokens(mint_client)

    async def check_balances(self) -> int:
        """Ensure the accounts we use have minimum balances for the test."""
        total_balance = 0
        expectations = [
            (self.minters, 2),
            (self.proxyminters, 2),
            (self.spammers, 3),
        ]

        for accounts, expected in expectations:
            for user in accounts:
                bal = self.w3.eth.get_balance(user.address)
                total_balance += bal
                if Web3.fromWei(bal, 'ether') < expected:
                    await self.hook(f'{user.username} below expected balance of {expected}')
        await self.hook('Done checking balances')
        return total_balance

    async def compute_nonce_total(self) -> int:
        """Compute the total nonce number; we can use the delta to determine how many tx were sent."""
        total_nonce = 0
        accounts = [self.deployer] + self.minters + self.proxyminters + self.spammers
        for user in accounts:
            total_nonce += self.w3.eth.get_transaction_count(user.address)
        return total_nonce

    async def verify_allowlist(self, mint_client: FastContractClient):
        """Ensure that we did the allow-listing properly."""
        addresses_to_allowlist = [m.address for m in self.minters] + self.deployed_proxies
        for address in addresses_to_allowlist:
            amt = mint_client.contract.functions.allowlist(address).call()
            if amt != 2:
                raise ValueError(f'User {address} expected 2 allowlist, got {amt}')
        await self.hook('Done checking allowlist')

    async def start_jobs(self, launcher: Launcher):
        """Start the minter, (possibly) the proxy minter, and the spammer jobs."""
        launcher.launch_minter()
        launcher.launch_proxyminters(self.deployed_proxies, self.proxyminters)
        launcher.launch_spammers(self.spammers)
        await self.hook('Done starting jobs')

    async def verify_jobs(self, launcher: Launcher):
        """Alert on the status of all the jobs we launched."""
        await self.hook(launcher.fetch_job_status())

    async def start_monitor(self, mint_contract: ChecksumAddress) -> BlockMonitor:
        """Watch for interactions with the contracts we've created."""
        monitored_contracts = [
            NamedContract('Spam  ', self.config.spammer_contract),
            NamedContract('Target', mint_contract),
        ]
        for i in range(len(self.deployed_proxies)):
            # These are optional now that we might not be using them.
            monitored_contracts.append(NamedContract(f'Proxy{i}', self.deployed_proxies[i]))

        monitor = BlockMonitor(self.w3, monitored_contracts, lambda msg: hook_it_async(self.config.monitor_hook, msg))
        self.tasks.append(asyncio.get_event_loop().create_task(monitor.start_scanning()))
        self.tasks.append(asyncio.get_event_loop().create_task(monitor.announce_init()))
        await self.hook('Done starting monitor')
        return monitor

    async def recover_tokens(self, mint_client: FastContractClient):
        """Recover the minted NFTs from the proxy contract."""
        token_count = mint_client.contract.functions.totalSupply().call()
        address_to_tokens = {Web3.toChecksumAddress(mint_client.contract.functions.ownerOf(i).call()): i
                             for i in range(token_count)}

        summary: list[str] = []
        for proxy_address in self.deployed_proxies:
            try:
                client = FastContractClient([self.w3], self.deployer.account,
                                            proxy_address, allowlist_proxy_abi())
                token_id = address_to_tokens[proxy_address]
                tx = client.send_contract_tx('withdraw', [token_id])
                receipt = client.get_receipt_by_hash(tx)
                status = 'success' if receipt['status'] else 'failure'
                summary.append(f'Token #{token_id} from  proxy {proxy_address} : {status}')
            except Exception as ex:
                summary.append(f'Failed to get token for {proxy_address} : {str(ex)}')

        for minter in self.minters:
            try:
                client = FastContractClient([self.w3], minter.account,
                                            mint_client.contract.address, flatlaunchpeg_abi())
                token_id = address_to_tokens[minter.address]

                cf = client.contract.functions.safeTransferFrom(minter.address, self.deployer.address, token_id)
                cf.call({'from': minter.address})
                tx = client.build_contract_tx(cf)
                tx_hash = client.sign_and_send_tx(tx)
                receipt = client.get_receipt_by_hash(tx_hash)
                status = 'success' if receipt['status'] else 'failure'
                summary.append(f'Token #{token_id} from EOA {minter.address} : {status}')
            except Exception as ex:
                summary.append(f'Failed to get token for {minter.address}: {str(ex)}')

        await self.hook('Done recovering tokens:\n' + '\n'.join(summary))
