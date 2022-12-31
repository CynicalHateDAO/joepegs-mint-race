# !/usr/bin/python
#
# Created this experiment to verify that TX are mined in the order that they're submitted.
# This *generally* seems to be the case but not always in this experiment. It's possible
# that this is due to the short timespan between submitting tx.

from client.web3_utils import make_avax_provider
from deployment.contracts.contracts import ACTION_CONTRACT_ADDRESS_FUJI, CONSUME_CONTRACT_ABI

from accounts.users import UserLoader
from client.endpoints import AVAX_NODE, FUJI_NODE
from client.fast_client import FastContractClient


def main():
    print('Loading')

    testnet = True
    node_uri = FUJI_NODE if testnet else AVAX_NODE
    providers = [make_avax_provider(node_uri)]
    contract_address = ACTION_CONTRACT_ADDRESS_FUJI if testnet else ''
    contract_abi = CONSUME_CONTRACT_ABI

    users = UserLoader.spammers()
    minters = [FastContractClient(providers, u.account, contract_address, contract_abi) for u in users]
    txs = []

    for i in range(len(minters)):
        minter = minters[i]
        minter.fixed_gas_in_gwei = 30
        minter.max_priority_fee_gwei = 1
        minter.gas_limit = 50_000
        txs.append(minter.send_contract_tx('consume', [i], None))

    for tx in txs:
        minters[0].get_receipt_by_hash(tx)


if __name__ == '__main__':
    main()
