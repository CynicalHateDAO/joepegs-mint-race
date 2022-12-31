import os
from typing import Any

import solcx
from eth_typing import ChecksumAddress

from client.web3_client import Web3Client

SPAMMER_CONTRACT_NAME = 'Spammoooor'
ALLOWLIST_PROXY_CONTRACT_NAME = 'AllowlistProxy'
COMPILER_VERSION = 'v0.8.4'


def load_web3_file(filename: str) -> str:
    dirname = os.path.dirname(os.path.realpath(__file__))
    path = os.path.join(dirname, 'files', filename)
    with open(path, 'r') as f:
        return f.read()


def launchpeg_factory_abi():
    return load_web3_file('launchpeg_factory.abi')


def flatlaunchpeg_abi():
    return load_web3_file('flatlaunchpeg.abi')


def spammer_abi():
    return load_web3_file('spammer.abi')


def spammer_solidity():
    return load_web3_file('spammer.sol')


def allowlist_proxy_solidity():
    return load_web3_file('allowlist_proxy.sol')


def allowlist_proxy_abi():
    return load_web3_file('allowlist_proxy.abi')


def deploy_contract(client: Web3Client, contract_name: str, source_code: str, *args: Any) -> ChecksumAddress:
    """Helper that will deploy a contract using the provided client.

    This is used to create the Spammer and Proxy contracts.
    The launchpegs are deployed from the launchpeg factory.
    """
    print(f'Ensuring compiler {COMPILER_VERSION} exists')
    solcx.install_solc(version=COMPILER_VERSION)
    solcx.set_solc_version(COMPILER_VERSION)

    print('Compiling deployment and extracting files/bytecode')
    compiled_contract = solcx.compile_source(source_code, output_values=['abi', 'bin'])
    abi = compiled_contract[f'<stdin>:{contract_name}']['abi']
    bytecode = compiled_contract[f'<stdin>:{contract_name}']['bin']

    contract = client.w3.eth.contract(abi=abi, bytecode=bytecode)
    tx_params = contract.constructor(*args).buildTransaction(client.build_base_tx())
    tx_hash = client.sign_and_send_tx(tx_params)

    tx_receipt = client.get_receipt_by_hash(tx_hash)
    if not tx_receipt['status']:
        raise Exception('Failed to deploy!')

    return tx_receipt.contractAddress
