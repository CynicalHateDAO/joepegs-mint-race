# !/usr/bin/python
#
# Utility for deploying the proxy minter contracts.

from absl import app, flags
from web3 import Web3

from accounts.users import UserLoader
from client.endpoints import make_avax_provider
from client.fast_client import FastContractClient
from client.web3_client import Web3Client
from deployment.contracts import deploy_contract, ALLOWLIST_PROXY_CONTRACT_NAME, allowlist_proxy_solidity, \
    allowlist_proxy_abi
from flood.env import Config, add_network_flag, add_mint_contract_flag


def main(_: list[str]):
    print('Loading')

    config = Config.from_flag()
    provider = make_avax_provider(config.provider_uris[0])
    user = UserLoader.deployer()
    client = Web3Client(provider, user.account)
    client.gas_limit = 5_000_000

    allowlist_proxy_address = deploy_contract(
        client, ALLOWLIST_PROXY_CONTRACT_NAME, allowlist_proxy_solidity(),
        Web3.toChecksumAddress(flags.FLAGS.mint_contract))

    client = FastContractClient([provider], user, allowlist_proxy_address, allowlist_proxy_abi())
    print('Deployed proxy to', allowlist_proxy_address)
    print('Remote has start time', client.contract.functions.allowlistStartTime().call())


if __name__ == '__main__':
    add_network_flag()
    add_mint_contract_flag()
    app.run(main)
