# !/usr/bin/python
#
# Created this experiment to verify that TX with equal gas_utilities settings are mined
# in the order that they're submitted.
#
# Tested with pauses between tx of .1s, .2s, still had incorrect ordering.
# Testing with .4s shows 100% correct ordering.
#
# Assumption is that there's something related to TX propagation taking place.
# But it does generally seem to hold that older TX are given preference.

import random
import time

from client.web3_utils import make_avax_provider
from deployment.contracts.contracts import ACTION_CONTRACT_ADDRESS_FUJI, CONSUME_CONTRACT_ABI

from accounts.users import UserLoader
from client.endpoints import AVAX_NODE, FUJI_NODE
from client.fast_client import MultiMintClient


def main():
    print('Loading')

    testnet = True
    node_uri = FUJI_NODE if testnet else AVAX_NODE
    providers = [make_avax_provider(node_uri)]
    contract_address = ACTION_CONTRACT_ADDRESS_FUJI if testnet else ''
    contract_abi = CONSUME_CONTRACT_ABI

    users = UserLoader.spammers()
    minters = [MultiMintClient(providers, u.account, contract_address, contract_abi, .5) for u in users]
    minters = [m for m in minters if m.get_balance() > 1]
    print('There are', len(minters), 'accounts ready to test with')
    txs = []

    # Shuffle the minters to make sure the high-gas_utilities ones run on different accounts each time.
    random.shuffle(minters)

    num_pauses = 5
    delay = .4
    # The first several minters will submit huge tx that block the chain.
    # The rest of the minters will (more slowly) be submitted and can be checked for ordering.
    for i in range(len(minters)):
        minter = minters[i]
        minter.fixed_gas_in_gwei = 30 if i > num_pauses else 40
        minter.max_priority_fee_gwei = 1 if i > num_pauses else 2
        minter.gas_limit = 100_000 if i > num_pauses else 7_901_000
        txs.append(minter.send_contract_tx('consume', [i], None))
        if i > num_pauses:
            time.sleep(delay)

    for tx in txs:
        minters[0].get_receipt_by_hash(tx)


if __name__ == '__main__':
    main()
