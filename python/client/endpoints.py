import random

from web3 import Web3
from web3.middleware import geth_poa_middleware

AVAX_NODE = 'https://api.avax.network/ext/bc/C/rpc'

# The default Avax RPC endpoint, but for websockets.
AVAX_WS_NODE = 'wss://api.avax.network/ext/bc/C/ws'

# If you're running a local avalanchego node.
LOCAL_NODE = 'http://127.0.0.1:9650/ext/bc/C/rpc'
LOCAL_WS_NODE = 'ws://127.0.0.1:9650/ext/bc/C/ws'

# Fuji testnet
FUJI_NODE = 'https://api.avax-test.network/ext/bc/C/rpc'
FUJI_CHAIN = 43113

# They have a priority endpoint that you have to deposit Ankr for. This is the free one.
ANKR_NODE = 'https://rpc.ankr.com/avalanche-c'

# Tests show this is slow?
POKT_NODE = 'https://avax-mainnet.gateway.pokt.network/v1/lb/605238bf6b986eea7cf36d5e/ext/bc/C/rpc'

QUICKNODE_OPTIONS = [
    'https://white-silent-butterfly.avalanche-mainnet.discover.quiknode.pro/b83ab9fe2f2f7b4579012f831a21a776fbfd7aaf/ext/bc/C/rpc',
    'https://icy-young-dew.avalanche-mainnet.discover.quiknode.pro/eb5680046599594a7598134a13d2cd2d3632d2ae/ext/bc/C/rpc',
    'https://snowy-winter-tree.avalanche-mainnet.discover.quiknode.pro/3b1972dc2daf58c013557dda3a5ca2a0506f5375/ext/bc/C/rpc',
    'https://dawn-silent-waterfall.avalanche-mainnet.discover.quiknode.pro/4b67e330535fb161229e629fe92c0eb5a54d3c1d/ext/bc/C/rpc',
    'https://nameless-bold-glitter.avalanche-mainnet.discover.quiknode.pro/08431917a2a2fc36ad07b5ffcad335bc9adb0779/ext/bc/C/rpc',
    'https://old-bold-field.avalanche-mainnet.discover.quiknode.pro/0ec1ad7428d6a6a170b6189111b79a36b1587e6b/ext/bc/C/rpc',
]


def random_quicknode() -> str:
    random.shuffle(QUICKNODE_OPTIONS)
    return QUICKNODE_OPTIONS[0]


BLAST_OPTIONS = [
    'https://ava-mainnet.blastapi.io/98685a70-3800-40b0-9b49-a41587ef86a1/ext/bc/C/rpc',
    'https://ava-mainnet.blastapi.io/6fbb8e65-7d5f-45b2-9745-eae730fd6977/ext/bc/C/rpc',
    'https://ava-mainnet.blastapi.io/6fbb8e65-7d5f-45b2-9745-eae730fd6977/ext/bc/C/rpc',
    'https://ava-mainnet.blastapi.io/ea9738aa-7340-44f6-a34e-ae4c1a46de3f/ext/bc/C/rpc',
    'https://ava-mainnet.blastapi.io/ea9738aa-7340-44f6-a34e-ae4c1a46de3f/ext/bc/C/rpc',
]


def random_blast() -> str:
    random.shuffle(BLAST_OPTIONS)
    return BLAST_OPTIONS[0]


DATAHUB_NODE = 'https://avalanche--mainnet--rpc.datahub.figment.io/apikey/1cd9e16b43abc1b1b3f7d8f14ec2a0f5/ext/bc/C/rpc'

DEFAULT_MULTIMINT_ENDPOINTS = [
    AVAX_NODE,
    random_quicknode(),
    random_blast(),
    DATAHUB_NODE,
]

FUJI_MULTIMINT_ENDPOINTS = [
    FUJI_NODE,
]

LOCAL_MULTIMINT_ENDPOINTS = [
    LOCAL_NODE
]


def make_provider(node_uri: str) -> Web3:
    if node_uri.startswith('http'):
        return Web3(Web3.HTTPProvider(node_uri))
    elif node_uri.startswith('ws'):
        return Web3(Web3.WebsocketProvider(node_uri))
    else:
        raise Exception(f'node_uri not valid: {node_uri}')


def make_avax_provider(node_uri: str) -> Web3:
    provider = make_provider(node_uri)
    # Inject the POA middleware
    provider.middleware_onion.inject(geth_poa_middleware, layer=0)
    return provider
