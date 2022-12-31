# tactical_retreat's Trader Joe mint race bot

This bot uses an unorthodox method to secure victory. Since we can't spam
transactions, and it's risky to guess when in advance to submit your TX,
I've come up with an alternate solution to ensuring my TX lands earlier
than other contestants.

## Flooding Avalanche

Avalanche only allows 8M gas per block. At a base gas price of 25, and AVAX at $20, it turns out that it's relatively
cheap and easy to stunlock the entire chain for a while.

Some resources:

* https://docs.avax.network/quickstart/adjusting-gas-price-during-high-network-activity
* https://docs.avax.network/quickstart/transaction-fees
* https://github.com/ava-labs/coreth/blob/master/consensus/dummy/consensus.go
* https://github.com/ava-labs/coreth/blob/master/consensus/dummy/dynamic_fees.go

The current target block rate is 1 block per 2 seconds. Blocks can be produced faster (to some degree) for an added fee,
with the limit being the amount of time required to reach consensus.

Some experimentation on Fuji shows that the gas fee for the block increases very slowly; on the order of 1-2 gas per
block that is full after the first few. A lot of gas needs to be consumed very consistently for gas prices to skyrocket.

## Why do we care?

We care because of this line in the documentation:

> Transactions are ordered by the priority fee, then the timestamp (*oldest first*).

Normally if you want your transaction to land earlier in the block, you bump the priority fee (or use a legacy style tx)
.
If someone happens to use the same gas as you, it's kind of a crapshoot who goes first (although there are some tricks
you can use).

The Trader Joe minting competition has a fixed gas price, and a random chance isn't good enough for me.

But if you can shut down the chain well in advance, then submit your TX, then unpause the chain when the TX need to be
evaluated... jackpot.

## Verifying this behavior

I could not find anything in the EVM that guarantees this ordering, so it's likely to be some emergent property of the
datastructures they're using to hold the TX and generate the blocks.

I did some experimentation to verify this on Fuji, and in local Avalanche..

## How to consume gas

Consuming gas is pretty trivial; you can deploy a contract that just wastes all the gas in the request every time. Then
you send a TX to that contract, and the TX gas limit worth of gas will be consumed.

## Gas consumption configuration

The TJ minting competition settings are:

* maxFeePerGas = 300 gwei (nAVAX)
* maxPriorityFeePerGas = 50 gwei (nAVAX)
* gasLimit = 300,000

We need to make sure there's less than 300K gas left in every block in the stunlock period. We also want to do this with
as few accounts as possible to save on gas.

8M / 299K = 26.7; so we'll use 27 accounts each sending the following TX:

* maxFeePerGas = 301 gwei (nAVAX)
* maxPriorityFeePerGas = 51 gwei (nAVAX)
* gasLimit = 299,999

Then another 3 accounts will send 100K gas requests; during testing I noticed that occasionally higher priority
transactions
could bump my spam TX out of the block, leaving a gap that mints could fit into. Since a mint costs about 105K gas,
using 100K
chunks should be fine.

How many transactions will be needed depends on how early the initializePhases request is sent. I've capped the amount
of time I'm willing to stunlock to 12 seconds. I estimate at most 10 TX per spammer will be needed.

Doing some handwavy math, it should cost 6-12 avax to execute this attack, or about .65 AVAX per block.

## Getting testnet AVAX

Getting testnet avax for a lot of accounts is a huge pain in the ass. But you can get 2 Fuji avax every day for every
account. The experimentation needs a fair amount of gas.

I wrote a script to scrape the fuji faucet for all my accounts and ran it for a few days, ending up with a lot of
testnet avax. But I think they noticed and got angry, because they shortly upgraded the security on the faucet.

Not sure how you can get a sizable chunk of testnet AVAX now. But you can do most of the testing on local avalanche
anyway.

# Mint contest prep work

Mint race contract:

* 0x0A50EE15688665C4bB98c802F5ee11fEc3DF0B80

Mint accounts created:

* 0x030c18274e67D52d9a0a209c516eA3B54c71b13c
* 0x4042630F7883f43E64690A73613125729d301fcD
* 0x1b22fB7A6818E9d84F94739e65024D02971413Df

Proxies deployed:

* 0x3bF6f6442e1eA7c6320a71C785355de936d0b3B7
* 0x9C3cF6F1Cfe83d9Cb0E43e3B97A5ABE0AEc66e1c
* 0x407961f3EaA2ffCAF621347887931b57d30A309B