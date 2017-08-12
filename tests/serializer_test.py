import datetime
import decimal
import enum
import uuid

from pytest import raises
from sqlalchemy.orm import relationship
from sqlalchemy.schema import Column, ForeignKey
from sqlalchemy.types import DateTime, Integer, Unicode

from iu.orm import Base
from iu.serializer import serialize


def test_serialize():
    with raises(NotImplementedError):
        serialize(Exception())


def test_serialize_primitives():
    assert serialize(None) is None
    assert serialize(True) is True
    assert serialize(1) == 1
    assert serialize(1.0) == 1.0
    assert serialize('str') == 'str'


def test_serialize_list():
    datetime_ = datetime.date(1993, 5, 16)
    assert serialize([1, datetime_]) == [1, '1993-05-16']


def test_serialize_set():
    datetime_ = datetime.date(1993, 5, 16)
    assert serialize({1, datetime_}) == {1, '1993-05-16'}


def test_serialize_dict():
    datetime_ = datetime.date(1993, 5, 16)
    expected = {'1': '1993-05-16', 'key': 'value'}
    assert serialize({1: datetime_, 'key': 'value'}) == expected


def test_serialize_enum():

    class DummyEnum(enum.Enum):
        a = 1
        b = datetime.date(1993, 5, 16)
        c = 'str'

    assert serialize(DummyEnum.a) == 1
    assert serialize(DummyEnum.b) == '1993-05-16'
    assert serialize(DummyEnum.c) == 'str'


def test_serialize_date():
    date_ = datetime.date(1993, 5, 16)
    datetime_ = datetime.datetime(
        1993, 5, 16, 9, 18, 23, 123456,
        datetime.timezone(datetime.timedelta(hours=9))
    )

    assert serialize(date_) == '1993-05-16'
    assert serialize(datetime_) == '1993-05-16T09:18:23.123456+09:00'


def test_serialize_decimal():
    assert serialize(decimal.Decimal('516.91800000')) == '516.918'
    assert serialize(decimal.Decimal('0.51691800')) == '0.516918'
    assert serialize(decimal.Decimal('516918000')) == '516918000'


def test_serialize_uuid():
    uuid_ = uuid.UUID('34408af8-9c23-4d07-8f1f-91da69c2f76e')
    assert serialize(uuid_) == '34408af8-9c23-4d07-8f1f-91da69c2f76e'


def test_serialize_db_model():

    class DummySubModel(Base):
        __tablename__ = 'dummy_sub_model'

        id = Column(Integer, primary_key=True)
        model_id = Column(Integer, ForeignKey('dummy_model.id'))
        a = Column(DateTime)
        b = Column(Unicode)

    class DummyModel(Base):
        __tablename__ = 'dummy_model'

        id = Column(Integer, primary_key=True)
        a = Column(DateTime)
        b = Column(Unicode)
        subs = relationship(DummySubModel)

    sub_models = [
        DummySubModel(
            id=5, model_id=23,
            a=datetime.datetime(1993, 5, 16, 9, 18, 23), b='sub-model1',
        ),
        DummySubModel(
            id=6, model_id=23,
            a=datetime.datetime(1994, 6, 17, 10, 19, 24), b='sub-model2',
        ),
    ]
    model = DummyModel(
        id=23,
        a=datetime.datetime(2008, 9, 18, 5, 16, 23), b='model',
        subs=sub_models,
    )
    serialized = serialize(model)
    serialized['subs'] = serialize(model.subs)
    assert serialized == {
        'id': 23,
        'a': '2008-09-18T05:16:23',
        'b': 'model',
        'subs': [
            {
                'id': 5,
                'model_id': 23,
                'a': '1993-05-16T09:18:23',
                'b': 'sub-model1',
            },
            {
                'id': 6,
                'model_id': 23,
                'a': '1994-06-17T10:19:24',
                'b': 'sub-model2',
            },
        ],
    }
