# !/usr/bin/python
#
# This job executes the actual mint using proxy contracts. Many of these jobs may
# be launched, in different regions. The proxy minter users all attempt to rapidly
# funnel mint transactions through the same 3 allowlisted mint contracts.

import concurrent
import random
import time
from asyncio import Future
from concurrent.futures import ThreadPoolExecutor

from absl import flags, app
from eth_typing import HexStr
from ratelimit import sleep_and_retry, limits
from web3 import Web3
from web3.types import Wei

from accounts.users import UserLoader
from client.endpoints import make_avax_provider
from client.fast_client import FastContractClient
from deployment.contracts import flatlaunchpeg_abi, allowlist_proxy_abi
from flood.discord import hook_it
from flood.env import add_network_flag, add_gas_flags, add_mint_contract_flag, Config
from flood.flood_configs import FloodGasSettings
from flood.flood_waiting import wait_until_flood_starts, watch_for_initialize_phases


def main(_: list[str]):
    print('Loading')
    config = Config.from_flag()
    FLAGS = flags.FLAGS

    mint_contract_address = Web3.toChecksumAddress(FLAGS.mint_contract)
    user_addresses = [Web3.toChecksumAddress(c) for c in FLAGS.user_addresses.split(',')]
    proxy_contract_addresses = [Web3.toChecksumAddress(c) for c in FLAGS.proxy_contracts.split(',')]
    max_gas = FLAGS.max_gas
    gas_tip = FLAGS.gas_tip
    gas_limit = FLAGS.gas_limit

    print('Loading:')
    print('  mint_contract:', mint_contract_address)
    print('  proxy_contracts:', proxy_contract_addresses)
    print('  max_gas:', max_gas)
    print('  gas_tip:', gas_tip)
    print('  gas_limit:', gas_limit)

    mint_contract_abi = flatlaunchpeg_abi()
    proxy_contract_abi = allowlist_proxy_abi()
    proxy_minters = UserLoader.proxy_minters()
    users = [u for u in proxy_minters if u.address in user_addresses]

    # We want each job to randomly prefer a contract instead of all jobs trying
    # to mint in the same order.
    random.shuffle(proxy_contract_addresses)

    pool = ThreadPoolExecutor()
    providers = [make_avax_provider(p) for p in config.provider_uris]
    mint_client = FastContractClient(providers, users[0].account, mint_contract_address, mint_contract_abi)
    proxy_clients = [FastContractClient(providers, users[i].account, proxy_contract_addresses[i], proxy_contract_abi)
                     for i in range(3)]
    for client in proxy_clients:
        client.max_gas_in_gwei = max_gas
        client.max_priority_fee_gwei = gas_tip
        client.gas_limit = gas_limit

    for proxy_address in proxy_contract_addresses:
        allowlisted_amount = mint_client.contract.functions.allowlist(proxy_address).call()
        if not allowlisted_amount:
            raise ValueError('Not allowlisted: ' + proxy_address)

    start_time = mint_client.contract.functions.allowlistStartTime().call()
    if start_time != 0:
        raise ValueError('Expected start time of 0 but got ' + start_time)

    address_text = '\n'.join([f'{pc.account.address} @ {pc.contract.address}' for pc in proxy_clients])
    hook_it(config.minter_hook, f'ProxyMinters ready: \n{address_text}')

    start_time = watch_for_initialize_phases(mint_client.contract)
    wait_until_flood_starts(start_time)

    tx_futures: list[Future[HexStr]] = []

    # We want to send requests as fast as we can, but not more than a few times per second.
    @sleep_and_retry
    @limits(calls=1, period=.6)
    def send_ratelimited_request():
        for proxy_client in proxy_clients:
            tx_f = pool.submit(proxy_client.send_contract_tx, 'remoteAllowlistMint', [], Wei(0))
            tx_futures.append(tx_f)

    # Send 10 TX as fast as we can, as long as we're before the start time.
    while time.time() < start_time and len(tx_futures) < 10:
        send_ratelimited_request()

    done, _ = concurrent.futures.wait(tx_futures, timeout=10)
    successes: list[str] = []
    for tx_future in done:
        tx_hash = tx_future.result()
        receipt = mint_client.get_receipt_by_hash(tx_hash)
        if receipt['status']:
            from_address = receipt['from']
            successes.append(f'{from_address} @ {tx_hash} -> success')

    hook_it(config.minter_hook, 'ProxyMinting Complete; status:\n' + '\n'.join(successes))


if __name__ == '__main__':
    add_mint_contract_flag()
    add_network_flag()
    add_gas_flags(FloodGasSettings())
    flags.DEFINE_string('proxy_contracts', None, 'csv of proxy contracts to use')
    flags.mark_flag_as_required('proxy_contracts')
    flags.DEFINE_string('user_addresses', None, 'csv of users to use to mint')
    flags.mark_flag_as_required('user_addresses')
    app.run(main)
