# !/usr/bin/python
#
# This script runs a full integration test against fuji or local avalanche.
# It requires the .env_<network> to be fully configured.

import json
import os.path
import shutil

from absl import app, flags
from dotenv import set_key

from accounts.users import UserLoader
from client.endpoints import make_avax_provider
from client.web3_client import Web3Client
from deployment.contracts import deploy_contract, SPAMMER_CONTRACT_NAME, spammer_solidity
from flood.env import add_network_flag, Config


def main(_: list[str]):
    network = flags.FLAGS.network
    env_file = f'.env_{network}'
    example_env_file = '.env.example'

    if not os.path.exists(env_file):
        shutil.copyfile(example_env_file, env_file)

    config = Config.from_flag()
    provider = make_avax_provider(config.provider_uris[0])
    user = UserLoader.deployer()
    client = Web3Client(provider, user.account)
    client.gas_limit = 5_000_000

    env = config.config
    if not env['BLOCK_TIME']:
        block_time = 1.0
        print('setting block time to', block_time)
        set_key(env_file, 'BLOCK_TIME', str(block_time), quote_mode='never')

    def unset_or_no_code(var_name: str):
        # Value could be unset on first run, or not have a deployment because it's
        # a local network that restarted, or just be a mistake.
        value = env[var_name]
        if not value:
            print('No value for', var_name)
            return True
        elif client.w3.eth.get_code(value) == b'':
            print('No code for', var_name, 'at', value)
            return True
        return False

    if unset_or_no_code('SPAMMER_CONTRACT_ADDRESS'):
        spammer_address = deploy_contract(client, SPAMMER_CONTRACT_NAME, spammer_solidity())
        set_key(env_file, 'SPAMMER_CONTRACT_ADDRESS', spammer_address, quote_mode='never')

    if unset_or_no_code('NOISE_CONTRACT_ADDRESS'):
        noise_address = deploy_contract(client, SPAMMER_CONTRACT_NAME, spammer_solidity())
        set_key(env_file, 'NOISE_CONTRACT_ADDRESS', noise_address, quote_mode='never')

    if unset_or_no_code('LAUNCHPEG_FACTORY_CONTRACT_ADDRESS'):
        launchpeg_dir = flags.FLAGS.launchpeg_dir
        if launchpeg_dir:
            factory_deployment = os.path.join(launchpeg_dir, 'deployments', network, 'LaunchpegFactory.json')
            if os.path.exists(factory_deployment):
                with open(factory_deployment, 'r') as f:
                    data = json.load(f)
                address = data['address']
                set_key(env_file, 'LAUNCHPEG_FACTORY_CONTRACT_ADDRESS', address, quote_mode='never')
            else:
                print(f'WARNING: LAUNCHPEG_FACTORY_CONTRACT_ADDRESS unset and {factory_deployment} does not exist')
        else:
            print('WARNING: LAUNCHPEG_FACTORY_CONTRACT_ADDRESS unset and launchpeg_dir not set')


if __name__ == '__main__':
    add_network_flag(default='local')
    flags.DEFINE_string('launchpeg_dir', None, 'path to the launchpeg repo')
    app.run(main)
