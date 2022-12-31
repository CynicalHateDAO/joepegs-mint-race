# !/usr/bin/python
#
# Utility to distribute funds from the deployer wallet to all generated wallets.
#
# Additionally, if running for the local chain, will prefund the deployer wallet
# from one of the known-key wallets.

from absl import app
from eth_account import Account
from web3 import Web3

from accounts.users import UserLoader
from client.endpoints import make_avax_provider
from client.web3_client import Web3Client
from flood.env import add_network_flag, Config

LOCAL_PREFUNDED_KEY = '56289e99c94b6912bfc12adc093c9b51124f0dc54ac7a766b2bc5ccf558d8027'


def main(_: list[str]):
    print('Loading')

    config = Config.from_flag()
    provider = make_avax_provider(config.provider_uris[0])
    user = UserLoader.deployer()
    client = Web3Client(provider, user.account)

    if config.is_local and client.get_balance() < 200:
        print('funding deployer')
        funded_client = Web3Client(provider, Account.from_key(LOCAL_PREFUNDED_KEY))
        tx = funded_client.build_send_value_tx(user.address, Web3.toWei(200, 'ether'))
        tx_hash = funded_client.sign_and_send_tx(tx)
        print(funded_client.get_receipt_by_hash(tx_hash))

    users = (UserLoader.spammers() + UserLoader.proxy_minters() +
             UserLoader.minters() + UserLoader.noisers())

    for u in users:
        bal = Web3.fromWei(provider.eth.get_balance(u.address), 'ether')
        if bal >= 4:
            print('skipping', u.username, u.address, int(bal))
            continue
        print('needs top up', u.username, u.address, int(bal))

        tx_hash = client.send_value(u.address, 2 if bal > 0 else 4)
        print(client.get_receipt_by_hash(tx_hash))


if __name__ == '__main__':
    add_network_flag()
    app.run(main)
