import asyncio
import time

from web3.contract import Contract

# This is how long we're willing to spam the network to secure the win.
# If the allowlist time is farther away than this, we'll wait until we're
# within the range.
FLOOD_DURATION_SEC = 20


def watch_for_initialize_phases(contract: Contract) -> int:
    """Synchronous method to scan for the initialized event (used in the minter/spammer jobs)."""
    change_filter = None
    while True:
        try:
            if change_filter is None:
                change_filter = contract.events.Initialized().createFilter(fromBlock='latest')
            for event in change_filter.get_new_entries():
                return event.args.allowlistStartTime
        except Exception as ex:
            print('Change filter failed, will recreate', ex)
            change_filter = None
            time.sleep(2)
        time.sleep(.1)


async def watch_for_initialize_phases_async(contract: Contract) -> int:
    """Asynchronous method to scan for the initialized event (used in the monitor)."""
    change_filter = None
    while True:
        try:
            if change_filter is None:
                print('Creating change filter for events')
                change_filter = contract.events.Initialized().createFilter(fromBlock='latest')
            for event in change_filter.get_new_entries():
                return event.args.allowlistStartTime
        except Exception as ex:
            print('Change filter failed, will recreate', ex)
            change_filter = None
            await asyncio.sleep(2)
        await asyncio.sleep(.1)


def wait_until_flood_starts(start_time: int):
    """Synchronously wait until we think it's acceptable to begin spamming."""
    while time.time() < start_time - FLOOD_DURATION_SEC:
        time.sleep(.01)


def oneshot_minter_extra_wait(start_time: int):
    """Apply a slight delay to the oneshot minter.

    There's a risk that the spammers don't come online fast enough to preempt
    the minter transaction from proceeding. This slight delay helps ensure that
    the minter gets jammed up.

    It's unclear how much time we'll have between the init and allowlist mint
    phase, so the delay scales downwards with that time.

    I don't want to sleep too long here though; there's the chance that some idiot
    who just mints / waits / mints / waits / exits is active, and they might get
    their tx in before me.

    Testing has shown that we only need a very minimal wait, if any.
    """
    time_to_start = start_time - int(time.time())
    if time_to_start > 3:
        time.sleep(.4)
    else:
        # Basically no time to risk sleeping, fire away.
        pass


def should_continue_spamming(start_time: int) -> bool:
    """For the proxy minter, stop spamming mint if we're past the mint start time."""
    return start_time > time.time()
