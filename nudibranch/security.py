from sqlalchemy.exc import OperationalError
from .models import Session, User


def check_user(username, password):
    session = Session()
    try:
        user = User.fetch_User(username)
    except OperationalError:
        return False
    return user and user.verify_password(password)


def group_finder(username, request):
    session = Session()
    user = User.fetch_User(username)
    if user:
        if user.is_admin:
            return ['admin']
        else:
            return ['student']
    else:
        return None
