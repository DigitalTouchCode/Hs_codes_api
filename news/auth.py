from django.conf import settings
from django.contrib.auth import get_user_model
from django.core import signing
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()

SIGNER_SALT = 'news.admin-token'
TOKEN_MAX_AGE = 60 * 60 * 8  # 8 hours — re-sign in with Google after this


def issue_admin_token(email):
    """A signed, tamper-proof token — not a session cookie, not a JWT
    library dependency. Django's own signing framework: the payload is
    just {'email': ...}, verified with a max age on each request."""
    return signing.dumps({'email': email}, salt=SIGNER_SALT)


class SignedTokenAuthentication(BaseAuthentication):
    """Reads `Authorization: Bearer <token>`, verifies it, and resolves
    it to a Django User with is_staff=True. Used only by the admin
    compose endpoints — the public post-listing endpoints don't need
    authentication at all."""

    def authenticate(self, request):
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return None

        token = auth_header[len('Bearer '):].strip()
        try:
            data = signing.loads(token, salt=SIGNER_SALT, max_age=TOKEN_MAX_AGE)
        except signing.BadSignature:
            raise AuthenticationFailed('Invalid or expired token — sign in again')

        email = data.get('email')
        if not email or email not in settings.NEWS_ADMIN_EMAILS:
            raise AuthenticationFailed('Not authorized for admin access')

        user, created = User.objects.get_or_create(
            username=email, defaults={'email': email, 'is_staff': True}
        )
        if not user.is_staff:
            user.is_staff = True
            user.save(update_fields=['is_staff'])

        return (user, None)

