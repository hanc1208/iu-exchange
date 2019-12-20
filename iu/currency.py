from sqlalchemy.orm import validates
from sqlalchemy.schema import CheckConstraint, Column
from sqlalchemy.sql.functions import func
from sqlalchemy.types import Integer, Numeric, Unicode
from typeguard import typechecked

from .orm import Base


class Currency(Base):
    id = Column(Unicode, primary_key=True)
    name = Column(Unicode, nullable=False)
    decimals = Column(Integer, nullable=False)
    confirmations = Column(Integer, nullable=False)
    minimum_deposit_amount = Column(Numeric(36, 18), nullable=False)
    minimum_withdrawal_amount = Column(Numeric(36, 18), nullable=False)
    withdrawal_fee = Column(Numeric(36, 18), nullable=False)
    latest_synced_block_number = Column(Integer, nullable=False)

    __tablename__ = 'currency'
    __table_args__ = (
        CheckConstraint(id == func.upper(id), 'ck_currency_id_upper'),
        CheckConstraint(decimals >= 0, 'ck_currency_decimals'),
    )

    @validates('id')
    @typechecked
    def validate_id(self, _, value: str) -> str:
        return value.upper()
