from __future__ import annotations
from sqlalchemy.ext.declarative import declared_attr
from sqlalchemy.schema import Column, ForeignKey
from sqlalchemy.types import Unicode

from iu.currency import Currency

from sqlalchemy.sql.functions import concat
from sqlalchemy.ext.hybrid import Comparator, hybrid_property
from typeguard import typechecked


class PairComparator(Comparator):

    def __eq__(self, other):
        if isinstance(other, str):
            o_base, o_quote = other.split('/')
        else:
            o_base, _, o_quote = other.expression.clause_expr.element.clauses
        base, _, quote = self.expression.clause_expr.element.clauses
        return (base == o_base) & (quote == o_quote)


class PairMixin:

    @declared_attr
    def base_currency(cls):
        return Column(Unicode, ForeignKey(Currency.id), nullable=False)

    @declared_attr
    def quote_currency(cls):
        return Column(Unicode, ForeignKey(Currency.id), nullable=False)

    @hybrid_property
    @typechecked
    def pair(self) -> str:
        return f'{self.base_currency}/{self.quote_currency}'

    @pair.comparator
    def pair(self):
        return PairComparator(
            concat(self.base_currency, '/', self.quote_currency)
        )

    @pair.setter
    @typechecked
    def pair(self, value: str) -> None:
        base_currency, quote_currency = value.split('/')
        self.base_currency = base_currency
        self.quote_currency = quote_currency


class PrimaryKeyPairMixin(PairMixin):

    @declared_attr
    def base_currency(cls):
        return Column(Unicode, ForeignKey(Currency.id), primary_key=True)

    @declared_attr
    def quote_currency(cls):
        return Column(Unicode, ForeignKey(Currency.id), primary_key=True)
