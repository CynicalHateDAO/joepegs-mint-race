# Experiments 

This directory holds a few experiments I ran to validate some assumptions about
how the avalanche blockchain works.

I did the ordering experiments against Fuji, and I later discovered that Fuji has
some peculiarities like a 1s blocktime, so unclear how useful these ended up being.

But I think the 'block the chain then submit in order and verify' test takes that
out of the equation so still probably OK.

TODO: come back and ensure all the experiments are runnable.

# Speed

I also tested the speed of various avax endpoints to accept transactions. I want
To put the higher speed endpoints higher in the list of providers.

At first I tried to get results from the WS endpoints but they seemed altogether
slower than the RPC ones, so I stopped that.


## Results 1

```
running 10 tests for 6 providers sending 1e-05 AVAX each time
0.793 ('https://api.avax.network/ext/bc/C/rpc', 'https://api.avax.network/ext/bc/C/rpc')
2.166 ('https://avax-mainnet.gateway.pokt.network/v1/lb/605238bf6b986eea7cf36d5e/ext/bc/C/rpc', 'https://avax-mainnet.gateway.pokt.network/v1/lb/605238bf6b986eea7cf36d5e/ext/bc/C/rpc')
0.16 ('https://white-silent-butterfly.avalanche-mainnet.discover.quiknode.pro/b83ab9fe2f2f7b4579012f831a21a776fbfd7aaf/ext/bc/C/rpc', 'https://white-silent-butterfly.avalanche-mainnet.discover.quiknode.pro/b83ab9fe2f2f7b4579012f831a21a776fbfd7aaf/ext/bc/C/rpc')
0.197 ('https://white-silent-butterfly.avalanche-mainnet.discover.quiknode.pro/b83ab9fe2f2f7b4579012f831a21a776fbfd7aaf/ext/bc/C/rpc', 'wss://white-silent-butterfly.avalanche-mainnet.discover.quiknode.pro/b83ab9fe2f2f7b4579012f831a21a776fbfd7aaf/ext/bc/C/ws')
0.438 ('https://avalanche--mainnet--rpc.datahub.figment.io/apikey/1cd9e16b43abc1b1b3f7d8f14ec2a0f5/ext/bc/C/rpc', 'https://avalanche--mainnet--rpc.datahub.figment.io/apikey/1cd9e16b43abc1b1b3f7d8f14ec2a0f5/ext/bc/C/rpc')
2.332 ('https://avalanche--mainnet--rpc.datahub.figment.io/apikey/1cd9e16b43abc1b1b3f7d8f14ec2a0f5/ext/bc/C/rpc', 'wss://avalanche--mainnet--rpc.datahub.figment.io/apikey/1cd9e16b43abc1b1b3f7d8f14ec2a0f5/ext/bc/C/ws')
```

## Results 2

```
0.792 ('https://api.avax.network/ext/bc/C/rpc', 'https://api.avax.network/ext/bc/C/rpc')
1.277 ('https://avax-mainnet.gateway.pokt.network/v1/lb/605238bf6b986eea7cf36d5e/ext/bc/C/rpc', 'https://avax-mainnet.gateway.pokt.network/v1/lb/605238bf6b986eea7cf36d5e/ext/bc/C/rpc')
0.225 ('https://nameless-bold-glitter.avalanche-mainnet.discover.quiknode.pro/08431917a2a2fc36ad07b5ffcad335bc9adb0779/ext/bc/C/rpc', 'https://nameless-bold-glitter.avalanche-mainnet.discover.quiknode.pro/08431917a2a2fc36ad07b5ffcad335bc9adb0779/ext/bc/C/rpc')
0.331 ('https://nameless-bold-glitter.avalanche-mainnet.discover.quiknode.pro/08431917a2a2fc36ad07b5ffcad335bc9adb0779/ext/bc/C/rpc', 'wss://nameless-bold-glitter.avalanche-mainnet.discover.quiknode.pro/08431917a2a2fc36ad07b5ffcad335bc9adb0779/ext/bc/C/ws')
0.489 ('https://avalanche--mainnet--rpc.datahub.figment.io/apikey/1cd9e16b43abc1b1b3f7d8f14ec2a0f5/ext/bc/C/rpc', 'https://avalanche--mainnet--rpc.datahub.figment.io/apikey/1cd9e16b43abc1b1b3f7d8f14ec2a0f5/ext/bc/C/rpc')
1.533 ('https://avalanche--mainnet--rpc.datahub.figment.io/apikey/1cd9e16b43abc1b1b3f7d8f14ec2a0f5/ext/bc/C/rpc', 'wss://avalanche--mainnet--rpc.datahub.figment.io/apikey/1cd9e16b43abc1b1b3f7d8f14ec2a0f5/ext/bc/C/ws')
```

# Results 3

Gave up on WS here, also on a different day.

```
0.765 https://api.avax.network/ext/bc/C/rpc
1.204 https://avax-mainnet.gateway.pokt.network/v1/lb/605238bf6b986eea7cf36d5e/ext/bc/C/rpc
0.286 https://ava-mainnet.blastapi.io/6fbb8e65-7d5f-45b2-9745-eae730fd6977/ext/bc/C/rpc
0.228 https://dawn-silent-waterfall.avalanche-mainnet.discover.quiknode.pro/4b67e330535fb161229e629fe92c0eb5a54d3c1d/ext/bc/C/rpc
0.542 https://avalanche--mainnet--rpc.datahub.figment.io/apikey/1cd9e16b43abc1b1b3f7d8f14ec2a0f5/ext/bc/C/rpc
```

# Results 4

Ran this in GCB us-east4.

# Final decision

AVAX, blast, quiknode, datahub in that order.

