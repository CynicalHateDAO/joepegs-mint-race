# !/usr/bin/python
#
# Test which endpoints are the fastest to accept transactions.
# Faster doesn't necessarily mean they're better to use, but we gotta go fast.
import time
from timeit import default_timer

from absl import app
from web3.types import Wei

from accounts.users import UserLoader
from client.endpoints import random_quicknode, random_blast, AVAX_NODE, DATAHUB_NODE, \
    make_avax_provider
from client.web3_client import Web3Client


def main(_: list[str]):
    print('Loading')

    from_user = UserLoader.deployer()
    to_address = from_user.address

    quicknode = random_quicknode()
    blast = random_blast()
    provider_uris = [
        AVAX_NODE,
        # ANKR_NODE,
        # POKT_NODE,
        blast,
        quicknode,
        DATAHUB_NODE,
    ]

    num_tests = 10
    print(f'running {num_tests} tests for {len(provider_uris)} providers sending 1 wei each time')
    for provider_uri in provider_uris:
        client = Web3Client(make_avax_provider(provider_uri), from_user.account)

        total_time = 0
        for i in range(num_tests):
            raw_tx = client.build_send_value_tx(to_address, Wei(1))
            signed_tx = client.sign_tx(raw_tx)

            start = default_timer()
            tx_hex = client.send_signed_tx(signed_tx)
            end = default_timer()

            total_time += end - start
            client.get_receipt_by_hash(tx_hex)
            time.sleep(2)

        took = round(total_time, 3)
        print(f'{took} {provider_uri}')


if __name__ == '__main__':
    app.run(main)
