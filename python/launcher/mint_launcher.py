from abc import ABC, abstractmethod

from eth_typing import ChecksumAddress

from accounts.users import User


class Launcher(ABC):
    """Interface for the job launcher."""

    @abstractmethod
    def launch_minter(self):
        """Launch a single minter job."""
        pass

    @abstractmethod
    def launch_proxyminters(self, proxies: list[ChecksumAddress], users: list[User]):
        """Launch as many proxy minter jobs as we have users / 3."""
        pass

    @abstractmethod
    def launch_spammers(self, users: list[User]):
        """Launch 30 spammer jobs.

        The first 27 jobs are the 'heavy' spammers that take up 100% of the 8M gas.
        The final 3 jobs are the 'light' spammers that consume space to block out
        mint requests, if something bumps one of the heavy spammers out.

        They all use a higher gas tip than the minter.
        """
        pass

    @abstractmethod
    def fetch_job_status(self) -> str:
        """Fetch human-readable data about the running jobs."""
        pass
