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
        try:
            response = self.get_response(request)
        finally:
            # Clear it once the request is done. WSGI workers reuse the
            # same OS thread for many requests, and threading.local()
            # persists across them -- without this, any code that runs
            # on this thread outside a request (a later request whose
            # AuthenticationMiddleware hasn't set request.user yet, a
            # background task, or -- as caught by the test suite -- a
            # rolled-back test transaction) could pick up a stale user
            # left over from whoever was last logged in on this thread.
            _user.value = None
        return response