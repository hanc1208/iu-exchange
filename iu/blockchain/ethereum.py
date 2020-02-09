import logging
from dataclasses import dataclass
import decimal
import uuid
from typing import List, Union

from ecdsa import SECP256k1, SigningKey
from pycoin.key.BIP32Node import BIP32Node
from typeguard import typechecked
from web3 import HTTPProvider, WebsocketProvider, Web3
from web3.utils.filters import Filter

from .base import BaseBlock, BaseBlockchain, BaseTransaction
from .util import uuid_to_bip44_path


logger = logging.getLogger(__name__)


def to_private_key(key) -> str:
    return Web3.toHex(key.secret_exponent())[2:]


def to_public_key(key) -> str:
    public_key = SigningKey.from_secret_exponent(
        key.secret_exponent(), curve=SECP256k1
    ).get_verifying_key().to_string().hex()
    return public_key


def to_address(key):
    return Web3.toChecksumAddress(
        Web3.toHex(Web3.sha3(hexstr=to_public_key(key))[-20:])
    )


@dataclass
class EthereumTransaction(BaseTransaction):
    pass


@dataclass
class EthereumBlock(BaseBlock):
    transactions: List[EthereumTransaction]


class EthereumBlockchain(BaseBlockchain):

    confirmations: int = 12
    currency_id: str = 'ETH'
    block_filter: Filter = None

    @typechecked
    def __init__(self, app) -> None:
        super().__init__(app)
        target_network = 'mainnet'
        host = f'{target_network}.infura.io'
        project_id = f''
        master_key = ''  # noqa
        websocket_provider_url = f'wss://{host}/ws/v3/{project_id}'
        http_provider_url = f'https://{host}/v3/{project_id}'
        self.web3 = Web3(WebsocketProvider(websocket_provider_url))  # noqa
        self.web3_http = Web3(HTTPProvider(http_provider_url))
        self.master_key = BIP32Node.from_hwif(master_key)
        self.prime_child_key = self.master_key.subkey_for_path("")

    @property
    @typechecked
    def master_address(self) -> str:
        return to_address(self.master_key)

    @typechecked
    def create_deposit_address(self, user_id: uuid.UUID) -> str:
        path = uuid_to_bip44_path(user_id)
        return to_address(self.prime_child_key.subkey_for_path(path))

    @typechecked
    def get_private_key(self, user_id: uuid.UUID) -> str:
        path = uuid_to_bip44_path(user_id)
        return to_private_key(self.prime_child_key.subkey_for_path(path))

    @typechecked
    def withdraw(self, address: str, amount: decimal.Decimal) -> str:
        raise NotImplementedError

    @typechecked
    def fetch_block(self, hash_or_number: Union[str, int]) -> EthereumBlock:
        while True:
            response = self.web3_http.eth.getBlock(
                hash_or_number, full_transactions=True,
            )
            if response:
                transactions = [
                    EthereumTransaction(
                        hash=transaction['hash'].hex(),
                        receiver=transaction['to'],
                        value=Web3.fromWei(
                            transaction['value'], unit='ether'
                        ),
                    )
                    for transaction in response['transactions']
                ]
                block = EthereumBlock(
                    number=response['number'],
                    hash=response['hash'].hex(),
                    parent_hash=response['parentHash'].hex(),
                    transactions=transactions,
                )
                return block
            logger.warning('Block is empty..')

    @typechecked
    def fetch_new_blocks(self, latest_block_number: int) -> List[EthereumBlock]:
        new_blocks = []
        new_block_hashes = self.block_filter.get_new_entries()
        for new_block_hash in new_block_hashes:
            if new_block_hash:
                new_block = self.fetch_block(new_block_hash.hex())
                if latest_block_number >= new_block.number:
                    continue
                new_blocks.append(self.fetch_block(new_block_hash.hex()))
            else:
                logger.warning('Empty hash?')
        return new_blocks

    @typechecked
    def send_transaction(
        self,
        *,
        private_key: str,
        to: str,
        amount: decimal.Decimal,
        fee_included: bool = False,
        gas_limit: int = 21000,
    ) -> str:
        gas_price = Web3.toInt(self.web3.eth.gasPrice)
        tx = {
            'nonce': self.web3.eth.getTransactionCount(
                self.web3.eth.account.privateKeyToAccount(private_key).address
            ),
            'gasPrice': gas_price,
            'gas': gas_limit,
            'to': to,
            'value': (
                Web3.toWei(amount, unit='ether') -
                (gas_price * gas_limit if fee_included else 0)
            ),
            'data': b'',
        }
        signed_transaction = self.web3.eth.account.signTransaction(
            tx, private_key=private_key,
        )
        tx_id = self.web3.eth.sendRawTransaction(
            signed_transaction.rawTransaction,
        ).hex()
        return tx_id

    @typechecked
    def validate_tx(self, tx: EthereumTransaction) -> bool:
        receipt = self.web3.eth.getTransactionReceipt(tx.hash)
        if receipt['status'] != 1:
            return False
        return super().validate_tx(tx)

    @typechecked
    def sync_init(self) -> None:
        self.block_filter = self.web3.eth.filter('latest')


if __name__ == '__main__':
    import toml
    from ..web.wsgi import create_wsgi_app
    with open('dev.toml') as f:
        config = toml.load(f)
    blockchain = EthereumBlockchain(create_wsgi_app(config))
    import pdb; pdb.set_trace()
    address = blockchain.create_deposit_address(uuid.UUID(''))
    key = blockchain.get_private_key(uuid.UUID(''))
    print(address)
    print(key)

# blockchain.sync()
