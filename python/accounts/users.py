from __future__ import annotations

import base64
import json
import os.path
import secrets
from dataclasses import dataclass
from enum import Enum
from functools import cached_property

import web3
from dacite import from_dict
from eth_account.signers.local import LocalAccount
from eth_typing import ChecksumAddress


@dataclass
class User(object):
    """Represents a user set up for the bot.

    The saddress is only used for manually reviewing the json.
    """
    username: str
    saddress: str
    obfuscated_private_key: str

    @staticmethod
    def build(username: str, private_key: str) -> User:
        """Create a user object from a username and private key."""
        account = web3.Account.from_key(private_key)
        obfuscated_key = obfuscate(private_key)
        return User(username=username, saddress=account.address, obfuscated_private_key=obfuscated_key)

    @staticmethod
    def new_account(username: str) -> User:
        """Generate a new private key for a user."""
        return User.build(username, "0x" + secrets.token_hex(32))

    @cached_property
    def account(self) -> LocalAccount:
        """Convert the user's obfuscated private key into an account (and cache it)."""
        return web3.Account.from_key(deobfuscate(self.obfuscated_private_key))

    @cached_property
    def address(self) -> ChecksumAddress:
        """Get the user's address from their account (and cache it)."""
        if self.saddress != self.account.address:
            raise Exception('Addresses do not match:', self.saddress, self.account.address)
        return self.account.address

    @property
    def name_address(self) -> str:
        """Helper for formatting the name/address nicely for logs."""
        return f'{self.username} / {self.address}'


class UserLoader(object):
    """Helper for loading, filtering, and saving a list of Users."""

    @staticmethod
    def deployer() -> User:
        return UserLoader(filename='users_deploy.json').users[0]

    @staticmethod
    def minters() -> list[User]:
        return UserLoader(filename='users_mint.json').users

    @staticmethod
    def proxy_minters() -> list[User]:
        return UserLoader(filename='users_proxymint.json').users

    @staticmethod
    def noisers() -> list[User]:
        return UserLoader(filename='users_noise.json').users

    @staticmethod
    def spammers() -> list[User]:
        return UserLoader(filename='users_spam.json').users

    def __init__(self, filename: str = 'users.json', must_exist: bool = True):
        self.filename = filename

        self.users: list[User] = []
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                data = json.load(f)
                for item in data:
                    self.users.append(from_dict(data_class=User, data=item))
        elif must_exist:
            raise ValueError(f'Expected {filename} to exist but it did not')

    def user_by_address(self, address: ChecksumAddress) -> User:
        for user in self.users:
            if user.address == address:
                return user
        raise ValueError('Could not find user with address ' + address)

    def generate_new_user(self, username: str):
        self.users.append(User.new_account(username))

    def save_users(self, allow_existing=False):
        if not allow_existing and os.path.exists(self.filename):
            raise ValueError(f'Cannot save users because {self.filename} exists')
        with open(self.filename, 'w') as f:
            dump_file(self.users, f)


def obfuscate(private_key: str) -> str:
    """A project-unique way to secure a private key."""
    encoded = base64.b64encode(private_key.encode('ascii')).decode('ascii')
    reversed_encoded = encoded[::-1]
    return reversed_encoded


def deobfuscate(obfuscated_key: str) -> str:
    """A project-unique way to reverse security on a private key."""
    encoded = obfuscated_key[::-1]
    data_str = base64.b64decode(encoded.encode('ascii'), validate=True).decode('ascii')
    return data_str


def dump_helper(x):
    """Standard helper for dumping a complex object to json."""
    if callable(x):
        return 'fn_obj'
    elif isinstance(x, Enum):
        return str(x)
    elif hasattr(x, '__dict__'):
        return vars(x)
    else:
        return repr(x)


def dump_file(obj, file, pretty=True):
    """Dump a complex object to a file."""
    indent = 4 if pretty else None
    json.dump(obj, file, indent=indent, sort_keys=True, default=dump_helper, ensure_ascii=False)
