import time
from importlib import import_module

from django.conf import settings
from django.contrib.sessions.backends.base import UpdateError
from django.contrib.sessions.exceptions import SessionInterrupted
from django.contrib.sessions.middleware import SessionMiddleware
from django.utils.cache import patch_vary_headers
from django.utils.http import http_date


class SeparateAdminSessionMiddleware(SessionMiddleware):
    """
    Middleware that separates admin database sessions from client storefront sessions.
    - Requests to /admin/... use the cookie configured in ADMIN_SESSION_COOKIE_NAME ('admin_sessionid').
    - Requests to the storefront (/index/, /shop/, /cart/, etc.) use SESSION_COOKIE_NAME ('eshop_sessionid').

    This prevents account collisions and auto-switching between the Django Admin database
    and client accounts, allowing both to be used at the same time in the same browser.
    """

    def get_cookie_name(self, request):
        path = request.path_info if hasattr(request, 'path_info') and request.path_info else request.path
        if path == '/admin' or (path.startswith('/admin/') and not path.startswith('/admin-dashboard')):
            return getattr(settings, 'ADMIN_SESSION_COOKIE_NAME', 'admin_sessionid')
        return getattr(settings, 'SESSION_COOKIE_NAME', 'eshop_sessionid')

    def process_request(self, request):
        cookie_name = self.get_cookie_name(request)
        session_key = request.COOKIES.get(cookie_name)
        request.session = self.SessionStore(session_key)
        request._session_cookie_name = cookie_name

    def process_response(self, request, response):
        """
        Save the session and set/delete the appropriate cookie based on whether
        the request was for the admin panel or the storefront.
        """
        try:
            accessed = request.session.accessed
            modified = request.session.modified
            empty = request.session.is_empty()
        except AttributeError:
            return response

        cookie_name = getattr(request, '_session_cookie_name', self.get_cookie_name(request))

        # First check if we need to delete this cookie.
        # The session should be deleted only if the session is entirely empty.
        if cookie_name in request.COOKIES and empty:
            response.delete_cookie(
                cookie_name,
                path=settings.SESSION_COOKIE_PATH,
                domain=settings.SESSION_COOKIE_DOMAIN,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )
            need_vary_cookie = True
        else:
            need_vary_cookie = accessed
            if (modified or settings.SESSION_SAVE_EVERY_REQUEST) and not empty:
                if request.session.get_expire_at_browser_close():
                    max_age = None
                    expires = None
                else:
                    max_age = request.session.get_expiry_age()
                    expires_time = time.time() + max_age
                    expires = http_date(expires_time)

                # Save the session data and refresh the client cookie.
                # Skip session save for 5xx responses.
                if response.status_code < 500:
                    try:
                        request.session.save()
                    except UpdateError:
                        raise SessionInterrupted(
                            "The request's session was deleted before the "
                            "request completed. The user may have logged "
                            "out in a concurrent request, for example."
                        )
                    response.set_cookie(
                        cookie_name,
                        request.session.session_key,
                        max_age=max_age,
                        expires=expires,
                        domain=settings.SESSION_COOKIE_DOMAIN,
                        path=settings.SESSION_COOKIE_PATH,
                        secure=settings.SESSION_COOKIE_SECURE or None,
                        httponly=settings.SESSION_COOKIE_HTTPONLY or None,
                        samesite=settings.SESSION_COOKIE_SAMESITE,
                    )
                    need_vary_cookie = True
        if need_vary_cookie:
            patch_vary_headers(response, ("Cookie",))
        return response
