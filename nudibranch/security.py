from pyramid.security import unauthenticated_userid
from .models import User


def get_user(request):
    user_id = unauthenticated_userid(request)
    if user_id is not None:
        return User.fetch_by_id(user_id)


def group_finder(user_id, request):
    user = request.user
    if user:
        return ['admin'] if user.is_admin else ['student']
