# !/usr/bin/python
#
# Little helper utility to check the balances across all wallets.

from absl import app

from accounts.users import UserLoader
from client.endpoints import make_avax_provider
from client.web3_client import Web3Client
from flood.env import Config, add_network_flag


def main(_: list[str]):
    print('Loading balance checker')

    config = Config.from_flag()
    provider = make_avax_provider(config.provider_uris[0])
    client = Web3Client(provider, None)

    users = ([UserLoader.deployer()] +
             UserLoader.minters() + UserLoader.proxy_minters() +
             UserLoader.noisers() + UserLoader.spammers())

    for user in users:
        client.account = user.account
        print(user.username, user.address, client.get_balance())


if __name__ == '__main__':
    add_network_flag()
    app.run(main)
