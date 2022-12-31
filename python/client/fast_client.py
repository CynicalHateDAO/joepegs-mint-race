import concurrent
import time
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Any, Optional

from eth_account.signers.local import LocalAccount
from eth_typing import ChecksumAddress
from eth_typing.encoding import HexStr
from hexbytes import HexBytes
from web3 import Web3
from web3.types import Wei, TxParams, Nonce

from client.web3_client import Web3Client


class FastContractClient(Web3Client):
    """Client for quickly sending contract transactions via multiple providers.

    Wraps a single contract. Keeps track of the nonce for speed.

    Generates a signed transaction and then distributes it to multiple providers
    in parallel, with a timeout.

    You should not attempt to send transactions more quickly than the send timeout,
    or you might experience nonce errors.
    """

    def __init__(self,
                 providers: list[Web3], account: LocalAccount,
                 contract_address: ChecksumAddress, contract_abi: str,
                 send_timeout_sec: float = .5):
        super().__init__(providers[0], account)
        self.providers = providers
        self.pool = ThreadPoolExecutor(max_workers=10)
        self.send_timeout_sec = send_timeout_sec

        # The deployment we're going to call.
        self.contract = self.w3.eth.contract(address=contract_address, abi=contract_abi)

        # This is state; updated after each TX.
        self._next_nonce = self.w3.eth.get_transaction_count(self.account.address)

    ####################
    # Sign & send Tx
    ####################

    def next_nonce(self) -> Nonce:
        """Use a cached nonce for the next one.

        Care is needed to manage updating this nonce, and to ensure that the same
        account is not using multiple clients that could be keeping track of different
        nonce values.
        """
        return self._next_nonce

    def send_contract_tx(self,
                         fn_name: str,
                         fn_args: list[Any],
                         payable_amount: Optional[Wei] = None) -> HexStr:
        """Helper for dynamically looking up a contract function and sending it.

        Utilizes the multisend function of this class.
        If payable_amount is non-None, a tx value is set.
        """
        dynamic_fn = self.contract.get_function_by_name(fn_name)
        cf = dynamic_fn(*fn_args)
        tx = self.build_contract_tx(cf)
        if payable_amount is not None:
            tx['value'] = payable_amount
        return self.sign_and_multisend_tx(tx)

    def sign_and_multisend_tx(self, tx: TxParams) -> HexStr:
        """Sign a transaction and sends it simultaneously via multiple providers."""
        signed_tx = self.w3.eth.account.sign_transaction(tx, self.account.privateKey)
        tx_hash = Web3.toHex(signed_tx.hash)

        tx_futures: list[Future[HexBytes]] = []
        start = time.time()
        try:
            for client in self.providers:
                tx_f = self.pool.submit(client.eth.send_raw_transaction, signed_tx.rawTransaction)
                tx_futures.append(tx_f)
        finally:
            # If we sent a tx, always need to update the nonce, even if an exception throws
            # us out of this method.
            self._next_nonce = Nonce(self._next_nonce + 1)

        # We only want to wait a limited amount of time for the TX to get sent.
        # This may cause some of the later, slower providers to fail. It's no big
        # deal, the earlier ones will have picked it up.
        done, timed_out = concurrent.futures.wait(tx_futures, timeout=self.send_timeout_sec)
        took = round(time.time() - start, 3)
        accepted = [x for x in done if x.exception() is None]
        print(f'Sent {len(tx_futures)} requests in {took};'
              f' {len(done)} done  {len(accepted)} accepted {len(timed_out)} timed out')

        if not accepted and done:
            # Something is fundamentally screwy; we should always have some TX accepted.
            # If none were accepted, surface the exception for debugging.
            raise list(done)[0].exception()

        return tx_hash
