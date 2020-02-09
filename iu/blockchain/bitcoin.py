from dataclasses import dataclass
import decimal
from typing import Any, Dict, List, Optional, Union
import uuid

from pycoin.key.BIP32Node import BIP32Node
from requests import post
from typeguard import typechecked

from .base import BaseBlock, BaseBlockchain, BaseTransaction
from .util import uuid_to_bip44_path


@dataclass
class BitcoinTransaction(BaseTransaction):
    tx_hash: str
    n: int

    @property
    @typechecked
    def hash(self) -> str:
        return f'{self.tx_hash}/{self.n}'

    @hash.setter
    @typechecked
    def hash(self, value: str) -> None:
        self.tx_hash = value


@dataclass
class BitcoinBlock(BaseBlock):
    transactions: List[BitcoinTransaction]


class BitcoinBlockchain(BaseBlockchain):

    confirmations = 1
    currency_id: str = 'BTC'

    @typechecked
    def __init__(self, app) -> None:
        super().__init__(app)
        test = True
        if test:
            host = 'localhost:18332'
            master_key = ''  # noqa
        else:
            host = 'localhost:8332'
            master_key = ''  # noqa
        rpc_user = 'iu-exchange'
        rpc_password = ''  # noqa
        self.provider_url = f'http://{host}/'
        self.auth = (rpc_user, rpc_password)
        self.master_key = BIP32Node.from_hwif(master_key)
        self.prime_child_key = self.master_key.subkey_for_path("44'/60'/0'/0")

    @property
    @typechecked
    def master_address(self) -> str:
        return self.master_key.address()

    @typechecked
    def rpc(self, method: str, params: Optional[List] = None):
        payload = {'jsonrpc': '1.0', 'method': method, 'params': params or []}
        response = post(self.provider_url, auth=self.auth, json=payload)
        response.raise_for_status()
        return response.json()['result']

    @staticmethod
    def parse_block(response: Dict[str, Any]) -> BitcoinBlock:
        return BitcoinBlock(
            number=response['height'],
            hash=response['hash'],
            parent_hash=response['previousblockhash'],
            transactions=[
                BitcoinTransaction(
                    hash=tx['txid'],
                    n=out['n'],
                    receiver=out['scriptPubKey']['addresses'][0],
                    value=decimal.Decimal(str(out['value'])),
                )
                for tx in response['tx']
                for out in tx['vout']
                if (
                    out['scriptPubKey']['type'] != 'nonstandard' and
                    out['value'] > 0
                )
            ]
        )

    @staticmethod
    @typechecked
    def satoshi_to_btc(satoshi: int) -> decimal.Decimal:
        return decimal.Decimal(satoshi) / (10 ** 8)

    @typechecked
    def create_deposit_address(self, user_id: uuid.UUID) -> str:
        path = uuid_to_bip44_path(user_id)
        return self.prime_child_key.subkey_for_path(path).address()

    @typechecked
    def get_private_key(self, user_id: uuid.UUID) -> str:
        path = uuid_to_bip44_path(user_id)
        return self.prime_child_key.subkey_for_path(path).secret_exponent()

    @typechecked
    def withdraw(self, address: str, amount: decimal.Decimal) -> str:
        raise NotImplementedError

    @typechecked
    def fetch_block(self, hash_or_number: Union[str, int],) -> BitcoinBlock:
        if isinstance(hash_or_number, int):
            block_hash = self.rpc('getblockhash', [hash_or_number])
        elif hash_or_number == 'latest':
            block_hash = self.rpc('getbestblockhash')
        else:
            block_hash = hash_or_number
        raw_response = self.rpc('getblock', [block_hash, 2])
        return BitcoinBlockchain.parse_block(raw_response)

    @typechecked
    def fetch_new_blocks(self, latest_block_number: int) -> List[BitcoinBlock]:
        response = self.rpc('getblockcount')
        return [
            self.fetch_block(n)
            for n in range(latest_block_number + 1, response['height'] + 1)
        ]

    @typechecked
    def send_transaction(
        self,
        *,
        private_key: str,
        to: str,
        amount: decimal.Decimal,
        fee_included: bool = False,
        **kwargs,
    ) -> str:
        raise NotImplementedError

    @typechecked
    def get_balance(self, address: str) -> decimal.Decimal:
        response = self.rpc('get', f'./rawaddr/{address}')
        return BitcoinBlockchain.satoshi_to_btc(response['final_balance'])

    @typechecked
    def validate_tx(self, tx: BitcoinTransaction) -> bool:
        return super().validate_tx()


if __name__ == '__main__':
    import toml
    from ..web.wsgi import create_wsgi_app
    with open('dev.toml') as f:
        config = toml.load(f)
    blockchain = BitcoinBlockchain(create_wsgi_app(config))
    blockchain.sync()
