class FloodGasSettings(object):
    """Utility for storing and converting gas values.

    We might use lower gas settings for testing purposes, but the way that
    the gas settings are permuted for different usages stays the same no
    matter the base gas setting.
    """

    def __init__(self, max_gas_gwei: int = 300, gas_tip_gwei: int = 50, gas_limit: int = 300_000):
        self.max_gas_gwei = max_gas_gwei
        self.gas_tip_gwei = gas_tip_gwei
        self.gas_limit = gas_limit

    def as_spam(self):
        """For the 'heavy' flood spammers."""
        return FloodGasSettings(max_gas_gwei=self.max_gas_gwei,
                                gas_tip_gwei=self.gas_tip_gwei + 1,
                                gas_limit=self.gas_limit - 1)

    def as_filler_spam(self):
        """For the flood spammers that fill in the gaps."""
        return FloodGasSettings(max_gas_gwei=self.max_gas_gwei,
                                gas_tip_gwei=self.gas_tip_gwei + 1,
                                gas_limit=self.gas_limit // 3)

    def as_loud_noise(self):
        """For noise transactions that preempt the spammer."""
        return FloodGasSettings(max_gas_gwei=self.max_gas_gwei,
                                gas_tip_gwei=self.gas_tip_gwei * 2,
                                gas_limit=30_000)

    def as_quiet_noise(self):
        """For noise transactions that get suppressed by the spammer."""
        return FloodGasSettings(max_gas_gwei=self.max_gas_gwei,
                                gas_tip_gwei=self.gas_tip_gwei // 2 + 1,
                                gas_limit=30_000)
