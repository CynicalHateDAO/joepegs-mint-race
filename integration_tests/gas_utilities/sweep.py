# !/usr/bin/python
#
# Utility to collect funds back from addresses to the deployer wallet.
# This is a bit less efficient than using a contract to split, but it
# is easy to write and integrates nicely with the local workflow.

from absl import app
from web3 import Web3
from web3.types import Wei

from accounts.users import UserLoader
from client.endpoints import make_avax_provider
from client.web3_client import Web3Client
from flood.env import Config, add_network_flag


def main(_: list[str]):
    print('Loading')

    config = Config.from_flag()
    provider = make_avax_provider(config.provider_uris[0])
    deployer = UserLoader.deployer()
    client = Web3Client(provider, None)
    client.max_gas_in_gwei = 30
    client.max_priority_fee_gwei = 1

    users = (UserLoader.spammers() + UserLoader.proxy_minters() +
             UserLoader.minters() + UserLoader.noisers())

    for u in users:
        client.account = u.account
        balance = client.get_balance_wei()

        gas_to_send = 22_000 * Web3.toWei(30, 'gwei')
        if balance < gas_to_send:
            print(f'Not collecting from {u.name_address}')
            continue

        amount_to_send = Wei(balance - gas_to_send)
        amt = round(Web3.fromWei(amount_to_send, 'ether'), 3)
        print(f'Collecting from {u.name_address} : {amt}')
        tx_hash = client.send_value_wei(deployer.address, amount_to_send)
        print(client.get_receipt_by_hash(tx_hash))


if __name__ == '__main__':
    add_network_flag()
    app.run(main)
