from pyramid.security import unauthenticated_userid
from .models import Session, User


def get_user(request):
    session = Session()
    user_id = unauthenticated_userid(request)
    if user_id is not None:
        return User.fetch_by_id(user_id)


def group_finder(user_id, request):
    user = request.user
    if user:
        if user.is_admin:
            return ['admin']
        else:
            return ['student']
    else:
        return None
