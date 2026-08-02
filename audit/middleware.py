from threading import local

_user = local()


def get_current_user():
    user = getattr(_user, 'value', None)
    if user is not None and not getattr(user, 'is_authenticated', False):
        return None
    return user


class CurrentUserMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _user.value = request.user
        response = self.get_response(request)
        return response