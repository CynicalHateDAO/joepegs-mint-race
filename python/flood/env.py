from __future__ import annotations

import random

from absl import flags
from dotenv import dotenv_values
from eth_typing import ChecksumAddress
from web3 import Web3

from client.endpoints import DEFAULT_MULTIMINT_ENDPOINTS, FUJI_MULTIMINT_ENDPOINTS, LOCAL_MULTIMINT_ENDPOINTS
from flood.flood_configs import FloodGasSettings

_MAINNET_VALUE = 'avalanche'
_TESTNET_VALUE = 'fuji'
_LOCAL_VALUE = 'local'


def add_network_flag(default: str = _LOCAL_VALUE):
    flags.DEFINE_enum('network', default,
                      (_MAINNET_VALUE, _TESTNET_VALUE, _LOCAL_VALUE),
                      'Avalanche net to connect to.')


def add_mint_contract_flag():
    flags.DEFINE_string('mint_contract', None, 'deployment to listen to for init event')
    flags.mark_flag_as_required('mint_contract')


def add_gas_flags(gas_settings: FloodGasSettings):
    flags.DEFINE_integer('max_gas', gas_settings.max_gas_gwei, 'max gas for transactions (in gwei)')
    flags.DEFINE_integer('gas_tip', gas_settings.gas_tip_gwei, 'gas tip for transactions (in gwei)')
    flags.DEFINE_integer('gas_limit', gas_settings.gas_limit, 'maximum gas units to use for transactions')


class Config(object):
    """Wrapper around the .env_<env> file with some helpers for env-specific stuff."""

    @staticmethod
    def from_flag() -> Config:
        return Config(flags.FLAGS.network)

    def __init__(self, network: str):
        self.network = network
        self.config = {} | dotenv_values(f'.env_{self.network}')

    @property
    def is_local(self):
        return self.network == _LOCAL_VALUE

    @property
    def provider_uris(self) -> list[str]:
        if self.network == _MAINNET_VALUE:
            return DEFAULT_MULTIMINT_ENDPOINTS
        elif self.network == _TESTNET_VALUE:
            return FUJI_MULTIMINT_ENDPOINTS
        elif self.network == _LOCAL_VALUE:
            return LOCAL_MULTIMINT_ENDPOINTS
        else:
            raise ValueError('not set up yet')

    @property
    def launchpeg_factory_contract(self) -> ChecksumAddress:
        return Web3.toChecksumAddress(self.config['LAUNCHPEG_FACTORY_CONTRACT_ADDRESS'])

    @property
    def spammer_contract(self) -> ChecksumAddress:
        return Web3.toChecksumAddress(self.config['SPAMMER_CONTRACT_ADDRESS'])

    @property
    def noise_contract(self) -> ChecksumAddress:
        return Web3.toChecksumAddress(self.config['NOISE_CONTRACT_ADDRESS'])

    @property
    def block_time(self) -> float:
        return float(self.config['BLOCK_TIME'])

    @property
    def orchestrator_hook(self) -> str:
        return self.config['ORCHESTRATOR_HOOK']

    @property
    def monitor_hook(self) -> str:
        return self.config['MONITOR_HOOK']

    @property
    def minter_hook(self) -> str:
        return self.config['MINTER_HOOK']

    @property
    def spammer_hook(self) -> str:
        idx = random.randint(1, 5)
        return self.config[f'SPAMMER_HOOK_{idx}']
