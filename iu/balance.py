from __future__ import annotations

import decimal

from sqlalchemy.sql.elements import BinaryExpression
from typing import Dict, Optional, Iterable, Tuple
import uuid

from flask.globals import current_app
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import relationship, validates
from sqlalchemy.schema import (
    CheckConstraint, Column, ForeignKey, UniqueConstraint,
)
from sqlalchemy.sql.expression import tuple_
from sqlalchemy.types import Numeric, Unicode
from sqlalchemy_utils.types.uuid import UUIDType
from typeguard import typechecked

from .currency import Currency
from .orm import Base, SessionType


class Balance(Base):
    user_id = Column(UUIDType, ForeignKey('user.id'), primary_key=True)
    user = relationship('User')
    currency = Column(
        Unicode, ForeignKey(Currency.id), primary_key=True, nullable=False,
    )
    amount = Column(Numeric(36, 18), nullable=False)
    locked_amount = Column(Numeric(36, 18), nullable=False)
    deposit_address = Column(Unicode, nullable=True)

    __tablename__ = 'balance'
    __table_args__ = (
        CheckConstraint(
            (amount >= 0) & (locked_amount >= 0) & (amount >= locked_amount),
            'ck_balance_amount',
        ),
        UniqueConstraint(currency, deposit_address),
    )

    @validates('amount')
    @typechecked
    def validate_amount(
        self, _, amount: decimal.Decimal,
    ) -> decimal.Decimal:
        assert amount >= (self.locked_amount or 0)
        return amount

    @validates('locked_amount')
    @typechecked
    def validate_locked_amount(
        self, _, locked_amount: decimal.Decimal,
    ) -> decimal.Decimal:
        assert 0 <= locked_amount <= (self.amount or 0)
        return locked_amount

    @typechecked
    def create_deposit_address(self) -> Optional[str]:
        if self.deposit_address:
            return
        if self.currency == 'ETH':
            from .blockchain.ethereum import EthereumBlockchain
            cls = EthereumBlockchain
        elif self.currency == 'BTC':
            from .blockchain.bitcoin import BitcoinBlockchain
            cls = BitcoinBlockchain
        else:
            raise ValueError(
                f'Currency {self.currency} does not support deposit'
            )
        blockchain = cls(current_app)
        self.deposit_address = blockchain.create_deposit_address(self.user_id)

    @hybrid_property
    @typechecked
    def usable_amount(self) -> Union[decimal.Decimal, BinaryExpression]:
        return self.amount - self.locked_amount

    @staticmethod
    @typechecked
    def create(
        session: SessionType, user_id: uuid.UUID, currency: str,
    ) -> Balance:
        balance = Balance(
            user_id=user_id,
            currency=currency,
            amount=decimal.Decimal(0),
            locked_amount=decimal.Decimal(0),
        )
        session.add(balance)
        return balance

    @staticmethod
    @typechecked
    def get_or_create(
        session: SessionType, user_id: uuid.UUID, currency: str,
        *, lock: bool = False,
    ) -> Balance:
        query = session.query(Balance)
        if lock:
            query = query.with_for_update()
        balance = query.get((user_id, currency.upper()))
        if not balance:
            balance = Balance.create(session, user_id, currency)
        return balance

    @staticmethod
    @typechecked
    def get_or_create_bulk(
        session: SessionType, keys: Iterable[Tuple[uuid.UUID, str]],
        *, lock: bool = False,
    ) -> Dict[Tuple[uuid.UUID, str], Balance]:
        query = session.query(Balance).filter(
            tuple_(Balance.user_id, Balance.currency).in_(keys)
        )
        if lock:
            query = query.with_for_update()
        balances = {(t.user_id, t.currency): t for t in query}
        for key in keys:
            if key not in balances:
                balances[key] = Balance.create(session, *key)
        return balances
