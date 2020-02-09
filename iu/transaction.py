import enum
import uuid
from typing import Dict

from flask.globals import current_app
from sqlalchemy.event import listens_for
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, joinedload, object_session
from sqlalchemy.schema import (
    CheckConstraint, Column, ForeignKey, ForeignKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.types import Integer, Numeric, Unicode
from sqlalchemy_enum34 import EnumType
from sqlalchemy_utc.now import utcnow
from sqlalchemy_utc.sqltypes import UtcDateTime
from sqlalchemy_utils.types.uuid import UUIDType
from typeguard import typechecked

from .balance import Balance
from .orm import Base, Session, SessionType


class TransactionType(enum.Enum):
    blockchain = 'blockchain'
    trade = 'trade'


class Transaction(Base):
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    created_at = Column(UtcDateTime, nullable=False, default=utcnow())
    type = Column(
        EnumType(TransactionType, name='transaction_type'),
        nullable=False, index=True,
    )
    user_id = Column(
        UUIDType, ForeignKey('user.id'), index=True, nullable=False,
    )
    user = relationship('User')
    currency = Column(
        Unicode, ForeignKey('currency.id'), index=True, nullable=False,
    )
    amount = Column(Numeric(36, 18), nullable=False)

    __tablename__ = 'transaction'
    __table_args__ = (
        CheckConstraint(amount != 0, 'ck_transaction_amount'),
    )
    __mapper_args__ = {
        'polymorphic_on': type,
        'polymorphic_identity': None,
        'with_polymorphic': '*',
    }


class BlockchainTransaction(Transaction):
    id = Column(
        UUIDType, ForeignKey('transaction.id'),
        default=uuid.uuid4, primary_key=True,
    )
    tx_id = Column(Unicode, ForeignKey('deposit.tx_id'), unique=True)

    __tablename__ = 'blockchain_transaction'
    __mapper_args__ = {
        'polymorphic_identity': TransactionType.blockchain,
    }


class TradeTransaction(Transaction):
    id = Column(
        UUIDType, ForeignKey('transaction.id'),
        default=uuid.uuid4, primary_key=True,
    )
    trade_id = Column(UUIDType, ForeignKey('trade.id'))
    trade = relationship('Trade')

    __tablename__ = 'trade_transaction'
    __mapper_args__ = {
        'polymorphic_identity': TransactionType.trade,
    }


class Deposit(Base):
    tx_id = Column(Unicode, primary_key=True)
    created_at = Column(UtcDateTime, nullable=False, default=utcnow())
    amount = Column(Numeric(36, 18), nullable=False)
    currency = Column(Unicode, ForeignKey('currency.id'), nullable=False)
    address = Column(Unicode, nullable=False)
    balance = relationship('Balance')
    user = association_proxy('balance', 'user')
    block_hash = Column(Unicode, nullable=False)
    block_number = Column(Integer, nullable=False)
    confirmed_block_hash = Column(Unicode, nullable=True)
    confirmed_at = Column(UtcDateTime, nullable=True)

    __tablename__ = 'deposit'
    __table_args__ = (
        ForeignKeyConstraint(
            (currency, address),
            ('balance.currency', 'balance.deposit_address'),
        ),
        CheckConstraint(
            confirmed_block_hash.is_(None) == confirmed_at.is_(None),
            'ck_deposit_confirmed',
        ),
        UniqueConstraint(currency, tx_id),
    )

    @staticmethod
    @typechecked
    def confirmed_query(
        *,
        currency: str,
        current_block_number: int,
        confirmations: int,
        session: SessionType,
    ):
        return session.query(Deposit).filter(
            Deposit.currency == currency,
            current_block_number >= Deposit.block_number + confirmations - 1,
            ~Deposit.confirmed,
        ).options(
            joinedload(Deposit.balance).joinedload(Balance.user),
        )

    @hybrid_property
    @typechecked
    def confirmed(self) -> bool:
        return self.confirmed_at is not None

    @confirmed.expression
    def confirmed(self):
        return self.confirmed_at.isnot(None)

    @typechecked
    def confirm(self, block_hash: str) -> None:
        session = object_session(self)
        self.confirmed_block_hash = block_hash
        self.confirmed_at = utcnow()
        transaction = BlockchainTransaction(
            user=self.balance.user,
            currency=self.currency,
            amount=self.amount,
            tx_id=self.tx_id,
        )
        session.add(transaction)


class Withdrawal(Base):
    id = Column(UUIDType, primary_key=True)
    created_at = Column(UtcDateTime, nullable=False, default=utcnow())
    user_id = Column(UUIDType, ForeignKey('user.id'), nullable=False)
    user = relationship('User')
    amount = Column(Numeric(36, 18), nullable=False)
    fee = Column(Numeric(36, 18), nullable=False)
    currency = Column(Unicode, ForeignKey('currency.id'), nullable=False)
    address = Column(Unicode, nullable=False)
    tx_id = Column(Unicode, nullable=True)
    block_hash = Column(Unicode, nullable=True)
    block_number = Column(Integer, nullable=True)
    approved_at = Column(UtcDateTime, nullable=True)
    rejected_at = Column(UtcDateTime, nullable=True)
    canceled_at = Column(UtcDateTime, nullable=True)

    __tablename__ = 'withdrawal'
    __table_args__ = (
        CheckConstraint(
            (block_hash.is_(None) == block_number.is_(None).self_group()) &
            (block_hash.is_(None) | tx_id.isnot(None)) &
            (tx_id.is_(None) | approved_at.isnot(None)) &
            (
                approved_at.is_(None) &
                rejected_at.is_(None) &
                canceled_at.is_(None) |
                (
                    approved_at.is_(None) !=
                    rejected_at.is_(None) !=
                    canceled_at.is_(None) &
                    (
                        approved_at.is_(None) |
                        tx_id.is_(None) &
                        block_hash.is_(None) &
                        block_number.is_(None)
                    )
                )
            ),
            'ck_withdrawal_state',
        ),
    )

    @hybrid_property
    @typechecked
    def pending(self) -> bool:
        return not self.approved and not self.rejected and not self.canceled

    @pending.expression
    def pending(self):
        return ~self.approved & ~self.rejected & ~self.canceled

    @hybrid_property
    @typechecked
    def approved(self) -> bool:
        return self.approved_at is not None

    @approved.expression
    def approved(self):
        return self.approved_at.isnot(None)

    @hybrid_property
    @typechecked
    def rejected(self) -> bool:
        return self.rejected_at is not None

    @approved.expression
    def rejected(self):
        return self.rejected_at.isnot(None)

    @hybrid_property
    @typechecked
    def canceled(self) -> bool:
        return self.canceled_at is not None

    @approved.expression
    def canceled(self):
        return self.canceled_at.isnot(None)

    @hybrid_property
    def locked_amount(self):
        return self.amount + self.fee

    @typechecked
    def unlock(self) -> None:
        assert self.pending
        balance = self.user.balance_of(self.currency, lock=True)
        balance.locked_amount -= self.locked_amount

    @typechecked
    def approve(self) -> None:
        session = object_session(self)
        self.unlock()
        self.approved_at = utcnow()
        transaction = BlockchainTransaction(
            user=self.user,
            currency=self.currency,
            amount=-self.locked_amount,
        )
        session.add(transaction)

    @typechecked
    def reject(self) -> None:
        self.unlock()
        self.rejected_at = utcnow()

    @typechecked
    def cancel(self) -> None:
        self.unlock()
        self.canceled_at = utcnow()

    @typechecked
    def withdraw(self) -> None:
        assert self.approved
        if self.currency == 'ETH':
            from .blockchain.ethereum import EthereumBlockchain
            Blockchain = EthereumBlockchain
        else:
            raise ValueError(
                f'Currency {self.currency} does not support withdrawal'
            )
        blockchain = Blockchain(current_app)
        self.tx_id = blockchain.withdraw(self.address, self.amount)


@listens_for(Session, 'before_flush')
def transaction_before_flush(session, _, __):
    from .exc import NotEnoughBalance
    from .user import User

    balance_map: Dict[uuid.UUID, Dict[str, Balance]] = {}

    @typechecked
    def balance_of(user: User, currency: str) -> Balance:
        _balance = balance_map.get(user.id, {}).get(currency)
        if not _balance:
            _balance = user.balance_of(currency, lock=True)
            balance_map.setdefault(user.id, {})[currency] = _balance
        return _balance

    for entity in session.new:
        if isinstance(entity, Transaction):
            balance = balance_of(entity.user, entity.currency)
            balance.amount += entity.amount
            if balance.usable_amount < 0:
                raise NotEnoughBalance()
        elif isinstance(entity, Withdrawal):
            balance = balance_of(entity.user, entity.currency)
            balance.locked_amount += entity.locked_amount
            if balance.usable_amount < 0:
                raise NotEnoughBalance()

    for entity in session.dirty:
        if not isinstance(entity, Balance):
            continue
        if hasattr(entity, '_no_orm_events'):
            continue
        user_id = entity.user_id
        currency = entity.currency
        balance_map.setdefault(user_id, {})[currency] = entity

    if balance_map:
        from .context import websocket_messages
        from .serializer import serialize
        websocket_messages.append({
            'type': 'balance',
            'data': serialize(balance_map),
        })
