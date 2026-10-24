import flask
from githubkit.auth import OAuthTokenAuthStrategy

TOKEN_SESSION_KEY = "github_token"
DATETIME_FIELDS = ("expire_time", "refresh_token_expire_time")


class TokenStore:
    """Keeps a user's GitHub tokens in ``flask.session``.

    With a server-side session backend such as Redis, the browser only holds
    the session id. Sessions are marked permanent, so
    ``PERMANENT_SESSION_LIFETIME`` is their expiry and each save resets it.
    """

    @staticmethod
    def save(token_auth: OAuthTokenAuthStrategy) -> None:
        data: dict[str, str | None] = {
            "token": token_auth.token,
            "refresh_token": token_auth.refresh_token,
        }
        for field in DATETIME_FIELDS:
            value = getattr(token_auth, field)
            data[field] = value.isoformat() if value else None

        flask.session.permanent = True
        if flask.session.get(TOKEN_SESSION_KEY) != data:
            flask.session[TOKEN_SESSION_KEY] = data
