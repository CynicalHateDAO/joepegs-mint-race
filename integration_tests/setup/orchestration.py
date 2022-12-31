import asyncio
import random
import time
import traceback
from asyncio import Task

import web3.logs
from eth_typing import ChecksumAddress
from web3 import Web3

from accounts.users import UserLoader, User
from client.endpoints import make_avax_provider
from client.fast_client import FastContractClient
from client.web3_client import Web3Client
from deployment.contracts import launchpeg_factory_abi, flatlaunchpeg_abi, spammer_abi, deploy_contract, \
    ALLOWLIST_PROXY_CONTRACT_NAME, allowlist_proxy_solidity, allowlist_proxy_abi
from flood.discord import hook_it_async
from flood.env import Config
from flood.flood_configs import FloodGasSettings
from launcher.gcb_mint_launcher import GcbLauncher
from launcher.local_mint_launcher import LocalLauncher
from launcher.mint_launcher import Launcher
from setup.block_monitor import BlockMonitor, NamedContract
from setup.noise import NoiseGenerator


class TestOrchestrator(object):
    """Starts, monitors, and cleans up after an integration test.

    There are a lot of phases to this, see _run() for more details.
    """

    def __init__(self, config: Config, duration: int, gas_settings: FloodGasSettings):
        self.config = config
        self.test_name = f'{self.config.network}_{duration}s_{gas_settings.gas_tip_gwei}tip'
        self.duration = duration
        self.gas_settings = gas_settings

        # We want to issue noise about once per block.
        self.noise_sleep_time_sec = self.config.block_time

        self.w3 = make_avax_provider(self.config.provider_uris[0])

        self.deployer = UserLoader.deployer()
        self.minters = UserLoader.minters()
        self.proxyminters = UserLoader.proxy_minters()
        self.spammers = UserLoader.spammers()
        self.noisers = UserLoader.noisers()

        # Contains the contracts we deploy to proxy-mint the launchpeg.
        self.deployed_proxies: list[ChecksumAddress] = []

        # Async jobs we start should get stuck in here so that we can cleanly
        # shut them down at the end (or we get annoying warnings).
        self.tasks: list[Task] = []

        # Jobs use different amounts of gas, shuffle the ordering a bit to make it less
        # likely for specific accounts to run out.
        random.shuffle(self.spammers)
        random.shuffle(self.noisers)

    async def hook(self, msg: str):
        """Sends a discord webhook as the orchestrator."""
        await hook_it_async(self.config.orchestrator_hook, msg)

    async def run(self):
        """Run the full test, catching errors and alerting on them."""
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

        # Deploy a new launchpeg.
        mint_contract = await self.deploy_flatlaunchpeg()

        # Create mint proxies for that launchpeg.
        await self.deploy_proxies(mint_contract)

        # The client we'll use to operate on the new launchpeg.
        mint_client = FastContractClient([self.w3], self.deployer.account,
                                         mint_contract, flatlaunchpeg_abi())

        # The contract starts out owned by the factory, so transfer it over to the
        # deployer so we can make the initPhases call later.
        await self.transfer_ownership(mint_client)

        # Put the 3 minters wallets and 3 proxy contracts in the allowlist.
        await self.populate_allowlist(mint_client)

        # Tiny wait to make sure that the node will return the right value.
        await asyncio.sleep(2)

        # Double check that didn't screw up.
        await self.verify_allowlist(mint_client)

        if self.config.network == 'local':
            # For local tests, we just start raw processes.
            job_sleep_time = 10
            job_launcher = LocalLauncher(mint_contract, self.config.network, self.gas_settings)
        else:
            # For mainnet/testnet tests, we start tasks on GCB.
            job_sleep_time = 100
            job_launcher = GcbLauncher(mint_contract, self.config.network, self.gas_settings)

        # Actually start all the jobs.
        await self.start_jobs(job_launcher)

        # The cloud build jobs in particular take a long time to start up.
        await asyncio.sleep(job_sleep_time)

        # Check that all the jobs are running, and alert if not.
        await self.verify_jobs(job_launcher)

        # Start outputting noise to get block production moving.
        if self.config.network != 'avalanche':
            await self.start_noise()

        # Start up the monitor function.
        monitor = await self.start_monitor(mint_contract)

        # Give things a few seconds to stabilize.
        await asyncio.sleep(5)

        # Kick off the initializePhases action.
        start_time = await self.initialize_phases(mint_client)

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
            ([self.deployer], 2),
            (self.minters, 2),
            (self.proxyminters, 2),
            (self.spammers, 3),
            (self.noisers, 1),
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
        accounts = [self.deployer] + self.minters + self.proxyminters + self.spammers+ self.noisers
        for user in accounts:
            total_nonce += self.w3.eth.get_transaction_count(user.address)
        return total_nonce

    async def deploy_flatlaunchpeg(self) -> ChecksumAddress:
        """Create a new flatlaunchpeg from the factory with an allowlist configured, and get the address."""
        deploy_client = FastContractClient([self.w3], self.deployer.account,
                                           self.config.launchpeg_factory_contract, launchpeg_factory_abi())
        deploy_client.gas_limit = 2_000_000
        tx = deploy_client.send_contract_tx('createFlatLaunchpeg', [
            'test',  # name
            'test',  # symbol
            self.deployer.address,  # project owner
            self.deployer.address,  # royalties to
            1,  # batch size
            100,  # max amount
            0,  # dev amount
            50,  # allowlist amount
            [50, 0, 0],  # batchreveal data
        ])
        receipt = deploy_client.get_receipt_by_hash(tx)
        if not receipt['status']:
            print(receipt)
            raise ValueError('Failed to createFlatLaunchpeg:', tx)

        events = deploy_client.contract.events.FlatLaunchpegCreated().processReceipt(receipt, errors=web3.logs.DISCARD)
        if not events:
            raise ValueError('No events in receipt:', tx)

        address = events[0].args.flatLaunchpeg
        await self.hook('Done createFlatLaunchpeg at ' + address)
        return Web3.toChecksumAddress(address)

    async def transfer_ownership(self, mint_client: FastContractClient):
        """Need to shift ownership of the contract from the factory to the deployer.

        Without this we won't be able to call initializePhases.
        """
        # Ownership is wrong by default on the new contract, transfer it.
        tx = mint_client.send_contract_tx('transferOwnership', [mint_client.account.address])
        receipt = mint_client.get_receipt_by_hash(tx)
        if not receipt['status']:
            raise ValueError('Failed to transferOwnership:', tx)
        await self.hook('Done transferOwnership')

    async def deploy_proxies(self, mint_contract: ChecksumAddress):
        """Create 3 different proxy contracts for minting the launchpeg."""
        client = Web3Client(self.w3, self.deployer.account)
        client.gas_limit = 2_000_000
        for _ in range(3):
            new_proxy = deploy_contract(client,
                                        ALLOWLIST_PROXY_CONTRACT_NAME,
                                        allowlist_proxy_solidity(),
                                        mint_contract)
            self.deployed_proxies.append(new_proxy)
        await self.hook('Done deploying proxies')

    async def populate_allowlist(self, mint_client: FastContractClient):
        """Ensure all the addresses that could mint, can mint 2.

        Although we only want to mint 1, we need to verify that we did only mint 1.
        """
        addresses_to_allowlist = [m.address for m in self.minters] + self.deployed_proxies
        allowlist_args = [
            addresses_to_allowlist,
            [2 for _ in addresses_to_allowlist],
        ]
        tx = mint_client.send_contract_tx('seedAllowlist', allowlist_args)
        receipt = mint_client.get_receipt_by_hash(tx)
        if not receipt['status']:
            raise ValueError('Failed to seedAllowlist:', tx)
        await self.hook('Done seedAllowlist')

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

    async def start_noise(self):
        """Create one noisemaker above the spam settings, and one below it."""

        def make_generator(settings: FloodGasSettings, user: User) -> NoiseGenerator:
            client = FastContractClient([self.w3], user.account, self.config.noise_contract, spammer_abi())
            client.max_gas_in_gwei = settings.max_gas_gwei
            client.max_priority_fee_gwei = settings.gas_tip_gwei
            client.gas_limit = settings.gas_limit
            return NoiseGenerator(client, self.noise_sleep_time_sec)

        quiet_noise = make_generator(self.gas_settings.as_quiet_noise(), self.noisers[0])
        loud_noise = make_generator(self.gas_settings.as_loud_noise(), self.noisers[1])

        self.tasks.append(asyncio.get_event_loop().create_task(quiet_noise.start_noise()))
        self.tasks.append(asyncio.get_event_loop().create_task(loud_noise.start_noise()))

        await self.hook('Done starting noise tasks')

    async def start_monitor(self, mint_contract: ChecksumAddress) -> BlockMonitor:
        """Watch for interactions with the contracts we've created."""
        monitored_contracts = [
            NamedContract('Spam  ', self.config.spammer_contract),
            NamedContract('Target', mint_contract),
            NamedContract('Noise ', self.config.noise_contract),
        ]
        for i in range(len(self.deployed_proxies)):
            # These are optional now that we might not be using them.
            monitored_contracts.append(NamedContract(f'Proxy{i}', self.deployed_proxies[i]))

        monitor = BlockMonitor(self.w3, monitored_contracts, lambda msg: hook_it_async(self.config.monitor_hook, msg))
        self.tasks.append(asyncio.get_event_loop().create_task(monitor.start_scanning()))
        self.tasks.append(asyncio.get_event_loop().create_task(monitor.announce_init()))
        await self.hook('Done starting monitor')
        return monitor

    async def initialize_phases(self, mint_client: FastContractClient) -> int:
        """Call initializePhases with an offset from the current time + duration + buffer."""
        old_priority = mint_client.max_priority_fee_gwei
        mint_client.max_priority_fee_gwei = 10
        now = int(time.time())
        allowlist_start = now + self.duration + 2
        tx = mint_client.send_contract_tx('initializePhases', [
            allowlist_start,
            allowlist_start + 60,  # public sale start time
            0,  # allowlist price
            0,  # public sale price
        ])
        mint_client.max_priority_fee_gwei = old_priority
        receipt = mint_client.get_receipt_by_hash(tx)
        if not receipt['status']:
            raise ValueError('Failed to initializePhases:', tx)
        await self.hook('Done initializePhases')

        return allowlist_start

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
