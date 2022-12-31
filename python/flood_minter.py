# !/usr/bin/python
#
# This job executes the actual mint. This is the 'single attempt' version.
# Only a single instance of this job is launched, and it does not attempt to
# spam requests.

import concurrent
from asyncio import Future
from concurrent.futures import ThreadPoolExecutor

from absl import flags, app
from eth_typing import HexStr
from web3 import Web3
from web3.types import Wei

from accounts.users import UserLoader
from client.endpoints import make_avax_provider
from client.fast_client import FastContractClient
from deployment.contracts import flatlaunchpeg_abi
from flood.discord import hook_it
from flood.env import add_network_flag, add_gas_flags, add_mint_contract_flag, Config
from flood.flood_configs import FloodGasSettings
from flood.flood_waiting import oneshot_minter_extra_wait, wait_until_flood_starts, watch_for_initialize_phases


def main(_: list[str]):
    print('Loading')
    config = Config.from_flag()
    FLAGS = flags.FLAGS

    mint_contract_address = Web3.toChecksumAddress(FLAGS.mint_contract)
    max_gas = FLAGS.max_gas
    gas_tip = FLAGS.gas_tip
    gas_limit = FLAGS.gas_limit

    print('Loading:')
    print('  mint_contract:', mint_contract_address)
    print('  max_gas:', max_gas)
    print('  gas_tip:', gas_tip)
    print('  gas_limit:', gas_limit)

    mint_contract_abi = flatlaunchpeg_abi()
    users = UserLoader.minters()

    pool = ThreadPoolExecutor()
    providers = [make_avax_provider(p) for p in config.provider_uris]
    clients = [FastContractClient(providers, user.account, mint_contract_address, mint_contract_abi)
               for user in users]
    for client in clients:
        client.max_gas_in_gwei = max_gas
        client.max_priority_fee_gwei = gas_tip
        client.gas_limit = gas_limit

        user_address = client.account.address
        allowlisted_amount = client.contract.functions.allowlist(user_address).call()
        if not allowlisted_amount:
            raise ValueError('Not allowlisted: ' + user_address)

    start_time = clients[0].contract.functions.allowlistStartTime().call()
    if start_time != 0:
        raise ValueError('Expected start time of 0 but got ' + start_time)

    address_text = '\n'.join([u.address for u in users])
    hook_it(config.minter_hook, f'Minters ready: \n{address_text}')

    start_time = watch_for_initialize_phases(clients[0].contract)
    wait_until_flood_starts(start_time)
    oneshot_minter_extra_wait(start_time)

    tx_futures: list[Future[HexStr]] = []
    for client in clients:
        tx_f = pool.submit(client.send_contract_tx, 'allowlistMint', [1], Wei(0))
        tx_futures.append(tx_f)

    done, _ = concurrent.futures.wait(tx_futures, timeout=10)
    logs: list[str] = []

    def check_for_remint(tx_hash: HexStr):
        """Process the receipts for each TX we've sent in parallel.

        If the TX got blocked appropriately by the spammer, this should be
        successful.

        If it did not, we should get a failure within a block or so. When
        that occurs, immediately attempt to resend the tx.

        A single TX should be sufficient, since we only get the failure a few
        seconds later after the block is miend.
        """
        receipt = clients[0].get_receipt_by_hash(tx_hash)
        status = 'success' if receipt['status'] else 'failure'
        from_address = receipt['from']
        logs.append(f'{from_address} @ {tx_hash} -> {status}')

        if not receipt['status']:
            print(f'TX failed; queuing for resend: {receipt}')
            for rm_client in clients:
                if rm_client.account.address != from_address:
                    continue
                rm_tx_hash = rm_client.send_contract_tx('allowlistMint', [1], Wei(0))
                rm_receipt = rm_client.get_receipt_by_hash(rm_tx_hash)
                rm_status = 'success' if rm_receipt['status'] else 'failure'
                logs.append(f'{from_address} @ {rm_tx_hash} -> {rm_status}')
                break

    remint_tx_futures: list[Future[HexStr]] = []
    for tx_future in done:
        tx_hash = tx_future.result()
        remint_future = pool.submit(check_for_remint, tx_hash)
        remint_tx_futures.append(remint_future)

    concurrent.futures.wait(remint_tx_futures, timeout=60)

    hook_it(config.minter_hook, 'Minting Complete; status:\n' + '\n'.join(logs))


if __name__ == '__main__':
    add_mint_contract_flag()
    add_network_flag()
    add_gas_flags(FloodGasSettings())
    app.run(main)
