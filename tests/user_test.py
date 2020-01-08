from typeguard import typechecked

from iu.user import User


@typechecked
def test_user_flask_login(fx_user: User):
    assert fx_user.get_id() == '00000000-0000-0000-0000-000000000001'
