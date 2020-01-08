import uuid

from flask_login.mixins import UserMixin
from sqlalchemy.schema import Column
from sqlalchemy_utc.now import utcnow
from sqlalchemy_utc.sqltypes import UtcDateTime
from sqlalchemy_utils.types.email import EmailType
from sqlalchemy_utils.types.uuid import UUIDType
from sqlalchemy_utils.types.password import PasswordType
from typeguard import typechecked

from .orm import Base


class User(Base, UserMixin):
    id = Column(UUIDType, primary_key=True, default=uuid.uuid4)
    created_at = Column(UtcDateTime, nullable=False, default=utcnow())
    email = Column(EmailType, nullable=False, unique=True)
    password = Column(PasswordType(schemes=['pbkdf2_sha512']), nullable=False)

    __tablename__ = 'user'

    @typechecked
    def get_id(self) -> str:
        return str(self.id)
