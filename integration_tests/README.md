# Running a local test

## Install avalanche runner / avalanchego

From the root of the project.

```bash
echo 'Fetching avalanchego'
mkdir -p bin/avalanchego
wget -q -P bin/avalanchego https://github.com/ava-labs/avalanchego/releases/download/v1.9.0/avalanchego-linux-amd64-v1.9.0.tar.gz
tar -xzf bin/avalanchego/avalanchego-linux-amd64-v1.9.0.tar.gz -C bin/avalanchego

echo 'Fetching avalanche network runner'
mkdir -p bin/runner
wget -q -P bin/runner https://github.com/ava-labs/avalanche-network-runner/releases/download/v1.2.3/avalanche-network-runner_1.2.3_linux_amd64.tar.gz
tar -xzf bin/runner/avalanche-network-runner_1.2.3_linux_amd64.tar.gz -C bin/runner
```

## Start local avalanche

First terminal (or background it).

```bash
bin/runner/avalanche-network-runner server \
    --log-level debug \
    --port=":8080" \
    --grpc-gateway-port=":8081"
```

Second terminal (if not backgrounding).

```bash
export AVALANCHEGO_EXEC_PATH=$(pwd)/bin/avalanchego/avalanchego-v1.9.0/avalanchego

bin/runner/avalanche-network-runner control start \
    --log-level debug \
    --endpoint="0.0.0.0:8080" \
    --number-of-nodes=5 \
    --avalanchego-path ${AVALANCHEGO_EXEC_PATH}

bin/runner/avalanche-network-runner control health \
    --log-level debug \
    --endpoint="0.0.0.0:8080"
```

To stop:

```bash
bin/runner/avalanche-network-runner control stop \
    --log-level debug \
    --endpoint="0.0.0.0:8080"
```

## Generate accounts, distribute funds, and configure the .env_local

```bash
python3.9 python/accounts/generate_accounts.py
python3.9 integration_tests/gas_utilities/distribute.py --network=local
python3.9 integration_tests/configure_env.py --network=local
```

## Deploy the launchpeg contracts

The latest TJ repo version isn't what's getting used for the contest. Also, I had to make a few other small tweaks.

So I cloned the appropriate sha and then patched a few edits on top. That repo can be found
at: https://github.com/tactical-retreat/tj-mint-race-launchpeg

```bash
# Substitute the correct path here for you
cd ../launchpeg
yarn hardhat deploy --network local
cd ../tj-mint-race

# Pick up the deployed launchpeg factory address
python3.9 integration_tests/configure_env.py --network=local --launchpeg_dir=../launchpeg
```

## Run the integration test

```bash
python3.9 integration_tests/run_test.py --network=local
```

## Run against fuji

The bot container needs to be rebuilt every time changes are made to stuff in `python`. You also need to have
distributed testnet avax to all the accounts.

```commandline
gcloud builds submit --config=gcb/build_bot.yaml --region=us-east4 .
```

To launch the test for fuji, just specify a different network.

```bash
python3.9 integration_tests/run_test.py --network=fuji
```
## Full remote integration test

I struggled an enormous amount trying to get a remote integration test working. I later found out that it wasn't
working because Cloud Build doesn't support IPv6 in the docker containers. Sigh.

I might come back and set up a VM-based solution.