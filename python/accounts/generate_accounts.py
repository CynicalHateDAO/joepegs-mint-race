# !/usr/bin/python
#
# Generate new users for the bot to use.
#
# Safe to run multiple times, but you should only need to run it one time
# locally.
#
# For remote integration tests it can be run on the fly; the wallets are
# funded from known wallets.

from absl import app

from accounts.users import UserLoader


def ensure_users(file_name: str, amount: int, user_type: str):
    loader = UserLoader(filename=file_name, must_exist=False)
    while len(loader.users) < amount:
        loader.generate_new_user(f'{user_type} {len(loader.users) + 1}')
    loader.save_users(allow_existing=True)


def main(_: list[str]):
    ensure_users('users_deploy.json', 1, 'Deployer')
    ensure_users('users_mint.json', 3, 'Minter')
    # Originally I was going to use 60 of these, but since winning with them
    # doesn't count anyway, heavily reduced..
    ensure_users('users_proxymint.json', 9, 'ProxyMinter')
    ensure_users('users_spam.json', 30, 'Spammer')
    ensure_users('users_noise.json', 2, 'Noise')


if __name__ == '__main__':
    app.run(main)
