# !/usr/bin/python
#
# This job issues the spam transactions. There should be 27 of these with one configuration
# and 3 of them with an alternate configuration.

import math
import time

from absl import flags, app
from web3 import Web3

from accounts.users import UserLoader
from client.endpoints import make_avax_provider
from client.fast_client import FastContractClient
from deployment.contracts import flatlaunchpeg_abi, spammer_abi
from flood.env import add_network_flag, add_gas_flags, add_mint_contract_flag, Config
from flood.flood_configs import FloodGasSettings
from flood.flood_waiting import wait_until_flood_starts, watch_for_initialize_phases


def main(_: list[str]):
    print('Loading')
    config = Config.from_flag()
    FLAGS = flags.FLAGS

    mint_contract_address = Web3.toChecksumAddress(FLAGS.mint_contract)
    spam_contract_address = config.spammer_contract
    user_address = Web3.toChecksumAddress(FLAGS.user_address)
    max_gas = FLAGS.max_gas
    gas_tip = FLAGS.gas_tip
    gas_limit = FLAGS.gas_limit
    block_time = config.block_time

    print('Loading:')
    print('  mint_contract:', mint_contract_address)
    print('  spam_contract:', spam_contract_address)
    print('  user_address:', user_address)
    print('  max_gas:', max_gas)
    print('  gas_tip:', gas_tip)
    print('  gas_limit:', gas_limit)
    print('  block_time:', block_time)

    mint_contract_abi = flatlaunchpeg_abi()
    spam_contract_abi = spammer_abi()

    user = UserLoader(filename='users_spam.json').user_by_address(user_address)

    providers = [make_avax_provider(p) for p in config.provider_uris]
    mint_client = FastContractClient(providers, user.account, mint_contract_address, mint_contract_abi)

    spam_client = FastContractClient(providers, user.account, spam_contract_address, spam_contract_abi)
    spam_client.max_gas_in_gwei = max_gas
    spam_client.max_priority_fee_gwei = gas_tip
    spam_client.gas_limit = gas_limit

    start_time = mint_client.contract.functions.allowlistStartTime().call()
    if start_time != 0:
        raise ValueError('Expected start time of 0 but got ' + start_time)

    name = f'{user.username} / {user.address}'
    print(f'{name} : ready')

    start_time = watch_for_initialize_phases(mint_client.contract)
    wait_until_flood_starts(start_time)

    all_tx = []

    time_until_start = start_time - time.time()
    blocks_until_start = math.ceil(time_until_start / block_time) + 4
    for i in range(blocks_until_start):
        new_tx = spam_client.send_contract_tx('consume', [i])
        all_tx.append(new_tx)

    print(f'{name} : finished submitting {len(all_tx)} tx')

    for tx_hash in all_tx:
        spam_client.get_receipt_by_hash(tx_hash)

    print('All TX mined; done')


if __name__ == '__main__':
    flags.DEFINE_string('user_address', None, 'user to spam as')
    flags.mark_flag_as_required('user_address')
    add_mint_contract_flag()
    add_network_flag()
    add_gas_flags(FloodGasSettings().as_spam())
    app.run(main)
