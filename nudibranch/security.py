from sqlalchemy.exc import OperationalError
from .models import Session, User


def group_finder(user_id, request):
    session = Session()
    user = User.fetch_user_by_id(user_id)
    if user:
        if user.is_admin:
            return ['admin']
        else:
            return ['student']
    else:
        return None
