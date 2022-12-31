import hashlib
import os
import subprocess
import sys

from eth_typing import ChecksumAddress

from accounts.users import User
from flood.flood_configs import FloodGasSettings
from launcher.mint_launcher import Launcher


class LocalLauncher(Launcher):
    """Utility for launching the mint/spam jobs locally on the machine."""

    MINTER_SCRIPT = 'python/flood_minter.py'
    PROXYMINTER_SCRIPT = 'python/flood_proxyminter.py'
    SPAMMER_SCRIPT = 'python/flood_spammer.py'

    def __init__(self, mint_contract: ChecksumAddress, network: str, gas_settings: FloodGasSettings):
        self.mint_contract = mint_contract
        self.network = network
        self.gas_settings = gas_settings

        self.minters_launched = 0
        self.proxyminters_launched = 0
        self.spammers_launched = 0

    def launch_minter(self):
        job_flags = self._common_flags(self.gas_settings)
        launch_job(LocalLauncher.MINTER_SCRIPT, job_flags)
        self.minters_launched += 1

    def launch_proxyminters(self, proxies: list[ChecksumAddress], users: list[User]):
        def launch_proxyminter(chunk_users: list[User]):
            if len(chunk_users) != 3:
                raise ValueError(f'Expected exactly 3 users, got {len(chunk_users)}')
            proxy_str = ','.join(proxies)
            user_str = ','.join([u.address for u in chunk_users])
            job_flags = self._common_flags(self.gas_settings) + [
                f'--user_addresses={user_str}',
                f'--proxy_contracts="{proxy_str}"',
            ]
            launch_job(LocalLauncher.PROXYMINTER_SCRIPT, job_flags)
            self.proxyminters_launched += 1

        for i in range(0, len(users), 3):
            launch_proxyminter(users[i:i + 3])

    def launch_spammers(self, users: list[User]):
        def launch_spammer(u: User, gas_settings: FloodGasSettings):
            job_flags = self._common_flags(gas_settings) + [f'--user_address="{u.address}"']
            launch_job(LocalLauncher.SPAMMER_SCRIPT, job_flags)
            self.spammers_launched += 1

        for user in users[:27]:
            launch_spammer(user, self.gas_settings.as_spam())
        for user in users[27:]:
            launch_spammer(user, self.gas_settings.as_filler_spam())

    def fetch_job_status(self) -> str:
        status = 'Job Status:'
        status += f'\n  {fetch_job_count(LocalLauncher.MINTER_SCRIPT)}/{self.minters_launched}'
        status += f'\n  {fetch_job_count(LocalLauncher.PROXYMINTER_SCRIPT)}/{self.proxyminters_launched}'
        status += f'\n  {fetch_job_count(LocalLauncher.SPAMMER_SCRIPT)}/{self.spammers_launched}'
        return status

    def _common_flags(self, gas: FloodGasSettings) -> list[str]:
        return [
            f'--mint_contract="{self.mint_contract}"',
            f'--network="{self.network}"',
            f'--max_gas="{gas.max_gas_gwei}"',
            f'--gas_tip="{gas.gas_tip_gwei}"',
            f'--gas_limit="{gas.gas_limit}"',
        ]


def launch_job(script: str, flags: list[str]):
    flag_contents = ' '.join(flags)
    cmd = f'python -u {script} {flag_contents}'
    log_file = '/tmp/' + hashlib.md5(cmd.encode()).hexdigest() + '.log'
    final_cmd = f'{cmd} > {log_file} &'
    print('executing:', final_cmd)
    os.system(final_cmd)


def fetch_job_count(tag: str) -> int:
    return int(_clean_subprocess(['bash', '-c', f'ps -alF --no-headers | grep {tag} | grep -v grep | wc -l']))


def _clean_subprocess(inputs: list[str]) -> str:
    return subprocess.check_output(inputs).decode(sys.stdout.encoding).strip()
