from discord_webhook import DiscordWebhook, AsyncDiscordWebhook


def hook_it(hook_address: str, msg: str):
    """Utility for logging a msg to console and also webhooking it (if configured)."""
    print('Webhook:', msg)
    if hook_address:
        msg = f'```{msg}```'
        DiscordWebhook(url=hook_address, content=msg,
                       rate_limit_retry=True, timeout=10).execute()


async def hook_it_async(hook_address: str, msg: str):
    """Utility for async logging a msg to console and also webhooking it (if configured)."""
    print('Webhook:', msg)
    if hook_address:
        msg = f'```{msg}```'
        await AsyncDiscordWebhook(url=hook_address, content=msg,
                                  rate_limit_retry=True, timeout=10).execute()
