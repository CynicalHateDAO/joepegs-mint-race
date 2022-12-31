import os
import subprocess
import sys

from eth_typing import ChecksumAddress

from accounts.users import User
from flood.flood_configs import FloodGasSettings
from launcher.mint_launcher import Launcher


class GcbLauncher(Launcher):
    """Utility for launching Cloud Build instances.

    Generally we're launching in us-east4, which is supposedly the closest
    to the majority of the avax validators.

    The proxy minter (if used) will be scattered more widely around the world
    though, since it only matters that one of them wins. Doesn't cost much.
    """

    # This is the closest region to the AWS region where many validators run.
    REGION = 'us-east4'

    # Generally we want to run in us-east-ish regions, but sprinkle some minters
    # around other regions just in case. Can't hurt.
    PROXY_REGIONS = [
        'us-east4',
        'us-central1',
        'us-west1',
        # When I was going to run a ton of these, having a lot of regions
        # made more sense.
        # 'us-east4', 'us-east4',
        # 'us-east4', 'us-east4',
        # 'us-central1', 'us-west1',
        # 'us-east1', 'us-east1',
        # 'europe-west1', 'asia-east1',
    ]

    MINTER_TAG = 'flood_bot_minter'
    PROXYMINTER_TAG = 'flood_bot_proxyminter'
    SPAMMER_TAG = 'flood_bot_spammer'

    def __init__(self, mint_contract: ChecksumAddress, network: str, gas_settings: FloodGasSettings):
        self.mint_contract = mint_contract
        self.network = network
        self.gas_settings = gas_settings

        self.minters_launched = 0
        self.proxyminters_launched = 0
        self.spammers_launched = 0

    def launch_minter(self):
        substitutions = self._common_substitutions(self.gas_settings)
        launch_job('gcb/bot_minter.yaml', GcbLauncher.REGION, substitutions)
        self.minters_launched += 1

    def launch_proxyminters(self, proxies: list[ChecksumAddress], users: list[User]):
        def launch_proxyminter(chunk_region: str, chunk_users: list[User]):
            if len(chunk_users) != 3:
                raise ValueError(f'Expected exactly 3 users, got {len(chunk_users)}')
            substitutions = self._common_substitutions(self.gas_settings) + [
                f'_USER_ADDRESS_0="{chunk_users[0].address}"',
                f'_USER_ADDRESS_1="{chunk_users[1].address}"',
                f'_USER_ADDRESS_2="{chunk_users[2].address}"',
                f'_PROXY_ADDRESS_0="{proxies[0]}"',
                f'_PROXY_ADDRESS_1="{proxies[1]}"',
                f'_PROXY_ADDRESS_2="{proxies[2]}"',
            ]
            launch_job('gcb/bot_proxyminter.yaml', chunk_region, substitutions)
            self.proxyminters_launched += 1

        # We don't have enough regions configured to fit as many proxies as we might
        # launch, so just replicate the list and pop from it as necessary.
        region_list_long = GcbLauncher.PROXY_REGIONS * 10
        for i in range(0, len(users), 3):
            region = region_list_long.pop(0)
            launch_proxyminter(region, users[i:i + 3])

    def launch_spammers(self, users: list[User]):
        def launch_spammer(u: User, gas_settings: FloodGasSettings):
            substitutions = self._common_substitutions(gas_settings) + [f'_USER_ADDRESS="{u.address}"']
            launch_job('gcb/bot_spammer.yaml', GcbLauncher.REGION, substitutions)
            self.spammers_launched += 1

        for user in users[:27]:
            launch_spammer(user, self.gas_settings.as_spam())
        for user in users[27:]:
            launch_spammer(user, self.gas_settings.as_filler_spam())

    def fetch_job_status(self) -> str:
        def fetch_status(tag: str, expected: int) -> str:
            working_total = 0
            queued_total = 0
            if tag == GcbLauncher.PROXYMINTER_TAG:
                for region in set(GcbLauncher.PROXY_REGIONS):
                    working, queued = fetch_job_statuses(region, tag)
                    working_total += working
                    queued_total += queued
            else:
                # We only need to scan one region for most jobs.
                working_total, queued_total = fetch_job_statuses(GcbLauncher.REGION, tag)
            return f'Tag={tag} ({working_total}/{expected}) running, {queued_total} queued'

        status = 'Job Status:'
        status += '\n  ' + fetch_status(GcbLauncher.MINTER_TAG, self.minters_launched)
        status += '\n  ' + fetch_status(GcbLauncher.PROXYMINTER_TAG, self.proxyminters_launched)
        status += '\n  ' + fetch_status(GcbLauncher.SPAMMER_TAG, self.spammers_launched)
        return status

    def _common_substitutions(self, gas: FloodGasSettings) -> list[str]:
        return [
            f'_MINT_CONTRACT="{self.mint_contract}"',
            f'_NETWORK="{self.network}"',
            f'_MAX_GAS="{gas.max_gas_gwei}"',
            f'_GAS_TIP="{gas.gas_tip_gwei}"',
            f'_GAS_LIMIT="{gas.gas_limit}"',
        ]


def launch_job(gcb_config_yaml: str, region: str, substitutions: list[str]):
    subst_contents = ','.join(substitutions)
    cmd = (f'gcloud builds submit'
           f' --config={gcb_config_yaml}'
           f' --region={region}'
           f' --no-source'
           f' --async'
           f' --substitutions={subst_contents}')
    print('Executing:', cmd)
    os.system(cmd)


def fetch_job_statuses(region: str, tag: str) -> (int, int):
    working = int(_clean_subprocess(
        ['bash', '-c',
         f'gcloud builds list --region={region} --filter=\'(status="WORKING" AND tags="{tag}")\' | wc -l']))
    queued = int(_clean_subprocess(
        ['bash', '-c',
         f'gcloud builds list --region={region} --filter=\'(status="QUEUED" AND tags="{tag}")\' | wc -l']))
    return int(working) - (1 if working else 0), int(queued) - (1 if queued else 0)


def _clean_subprocess(inputs: list[str]) -> str:
    return subprocess.check_output(inputs).decode(sys.stdout.encoding).strip()
