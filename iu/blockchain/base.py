import contextlib
import decimal
import logging
import uuid
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Union

from typeguard import typechecked

from ..balance import Balance
from ..currency import Currency
from ..orm import SessionType, create_session
from ..transaction import Deposit


@dataclass
class BaseTransaction:
    hash: str
    receiver: str
    value: int

    @typechecked
    def get_quantized_value(self, decimals: int) -> decimal.Decimal:
        return decimal.Decimal(self.value).quantize(
            decimal.Decimal(10) ** -decimals,
            rounding=decimal.ROUND_DOWN,
        )


@dataclass
class BaseBlock:
    number: int
    hash: str
    parent_hash: str
    transactions: List[BaseTransaction]


class BaseBlockchain:

    confirmations: int = NotImplemented
    polling_interval: int = 15
    currency_id: str = NotImplemented
    currency: Currency = None
    session: SessionType = None
    master_address: str = NotImplemented

    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger(
            f'{self.__class__.__module__}.{self.__class__.__qualname__}'
        )
        self.alive = False

    @contextlib.contextmanager
    def context(self):
        try:
            self.alive = True
            self.session = create_session(self.app)
            self.currency = self.session.query(
                Currency
            ).filter(
                Currency.id == self.currency_id,
            ).with_for_update(
                skip_locked=True,
            ).first()
            if not self.currency:
                raise ValueError(f'Currency {self.currency_id} has been locked')
            print(f'Currency: {self.currency_id}; Ready')
            print(f'Master address: {self.master_address}')
            yield
        finally:
            self.currency = None
            if self.session:
                self.session.close()
                self.session = None
            self.alive = False

    @typechecked
    def create_deposit_address(self, user_id: uuid.UUID) -> str:
        raise NotImplementedError

    @typechecked
    def get_private_key(self, user_id: uuid.UUID) -> str:
        raise NotImplementedError

    @typechecked
    def withdraw(self, address: str, amount: decimal.Decimal) -> str:
        raise NotImplementedError

    @typechecked
    def fetch_block(self, hash_or_number: Union[str, int]) -> BaseBlock:
        raise NotImplementedError

    @typechecked
    def sync_init(self) -> None:
        pass

    @typechecked
    def fetch_new_blocks(self, latest_block_number: int) -> List[BaseBlock]:
        raise NotImplementedError

    @typechecked
    def process_deposits(self, block: BaseBlock):
        deposits = Deposit.confirmed_query(
            currency=self.currency_id,
            current_block_number=block.number,
            confirmations=self.confirmations,
            session=self.session,
        )
        for deposit in deposits:
            try:
                tx_id = self.send_transaction(
                    private_key=self.get_private_key(deposit.user.id),
                    to=self.master_address,
                    amount=deposit.amount,
                    fee_included=True,
                )
                self.logger.info(f'Collecting {deposit.tx_id}: {tx_id}')
            except ValueError as e:
                self.logger.exception(str(e))
                continue
            if int(tx_id, 0) == 0:
                self.logger.error('zero hash detected')
                continue
            deposit.confirm(block.hash)
            self.logger.info(
                f'Confirmed {deposit.tx_id} '
                f'at {block.number} from {deposit.block_number}: '
                f'{deposit.amount} {self.currency_id}'
            )
        self.currency.latest_synced_block_number = block.number

    @typechecked
    def create_deposit(self, block: BaseBlock, tx: BaseTransaction) -> Deposit:
        return Deposit(
            currency=self.currency_id,
            address=tx.receiver,
            tx_id=tx.hash,
            block_hash=block.hash,
            block_number=block.number,
            amount=tx.get_quantized_value(self.currency.decimals),
        )

    @typechecked
    def sync_block(self, block: BaseBlock) -> None:
        with self.session.no_autoflush:
            self.logger.info(f'Syncing block {block.number} {block.hash}')
            if self.session.query(
                self.session.query(Deposit).filter(
                    Deposit.block_hash == block.hash
                ).exists()
            ).scalar():
                return
            tx_map: Dict[str, List[BaseTransaction]] = {}
            for tx in block.transactions:
                if not self.validate_tx(tx):
                    continue
                tx_map.setdefault(tx.receiver, []).append(tx)
            matched_addresses = {
                address
                for address, in self.session.query(
                    Balance.deposit_address.distinct()
                ).filter(
                    Balance.currency == self.currency_id,
                    Balance.deposit_address.in_(tx_map.keys())
                )
            }
            for matched_address in matched_addresses:
                for tx in tx_map[matched_address]:
                    deposit = self.create_deposit(block, tx)
                    self.session.add(deposit)
                    self.logger.info(
                        f'Deposit {deposit.block_number}: '
                        f'{deposit.amount} {self.currency_id}, '
                        f'{deposit.tx_id}'
                    )
            self.process_deposits(block)
            with self.app.test_request_context():
                self.session.commit()

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
        raise NotImplementedError

    @typechecked
    def validate_tx(self, tx: BaseTransaction) -> bool:
        if tx.value <= 0:
            return False
        if not tx.receiver:
            return False
        value = tx.get_quantized_value(self.currency.decimals)
        if value < self.currency.minimum_deposit_amount:
            return False
        return True

    @typechecked
    def sync(self) -> None:
        self.sync_init()

        start_number = (
            self.currency.latest_synced_block_number - self.confirmations + 1
        )
        latest_block = self.fetch_block('latest')

        print(f'Sync {start_number}…{latest_block.number}')
        from concurrent.futures.thread import ThreadPoolExecutor

        sync_count = 10
        blocks = []
        for index in range(start_number, latest_block.number + 1, sync_count):
            if not self.alive:
                return
            with ThreadPoolExecutor(sync_count) as executor:
                block_numbers = range(
                    index, min(latest_block.number, index + sync_count),
                )
                new_blocks = sorted(
                    executor.map(self.fetch_block, block_numbers),
                    key=lambda b: b.number,
                )
            for block in new_blocks:
                self.sync_block(block)
            blocks.extend(new_blocks)

        blocks.append(latest_block)
        self.sync_block(latest_block)

        print('Fetching', end='', flush=True)
        while self.alive:
            print('.', end='', flush=True)
            try:
                new_blocks = self.fetch_new_blocks(blocks[-1].number)
            except ValueError:
                self.sync()
                return
            if new_blocks:
                print()
            for new_block in new_blocks:
                blocks.append(new_block)
                index = -1
                while (
                    len(blocks) + index > 0 and
                    blocks[index].parent_hash != blocks[index - 1].hash
                ):
                    print(f'Fix head.. {index}')
                    self.session.query(Deposit).filter(
                        Deposit.block_hash == blocks[index - 1].hash
                    ).delete()
                    blocks[index - 1] = (
                        self.fetch_block(blocks[index - 1].number)
                    )
                    self.sync_block(blocks[index - 1])
                    index -= 1
                self.sync_block(new_block)
            if new_blocks:
                print('Fetching', end='', flush=True)
            time.sleep(self.polling_interval)
