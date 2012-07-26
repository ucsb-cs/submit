from sqlalchemy.exc import OperationalError
from .models import Session, User


def group_finder(username, request):
    session = Session()
    user = User.fetch_user(username)
    if user:
        if user.is_admin:
            return ['admin']
        else:
            return ['student']
    else:
        return None
