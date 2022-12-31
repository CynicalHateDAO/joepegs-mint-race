# Python code

This folder contains all the code required to run the final contest mint bot.

You will need to have built the bot container already; see the `gcb` folder readme
for more information on that.

You'll also need to have configured the users and spread out the avax; see the
`integration_testing` folder for information on that. The docs there are geared
towards setting up testing, but you can reuse the same stuff with `--network=avalanche`
to prep for the contest.

I've hardcoded a few things into the contest minter, so launching it is pretty simple:

```commandline
python3.9 python/run_contest.py
```

This will take care of validating the setup, starting the monitoring, launching the jobs, etc.