from datetime import datetime

import flask
from githubkit.auth import OAuthTokenAuthStrategy
from githubkit.exception import AuthCredentialError

from .configuration import OAuthConfiguration

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

    @staticmethod
    def load(configuration: OAuthConfiguration) -> OAuthTokenAuthStrategy | None:
        data = flask.session.get(TOKEN_SESSION_KEY)
        if not isinstance(data, dict):
            return None

        try:
            return OAuthTokenAuthStrategy(
                client_id=configuration.client_id,
                client_secret=configuration.client_secret,
                token=data.get("token"),
                refresh_token=data.get("refresh_token"),
                **{
                    field: datetime.fromisoformat(data[field])
                    if data.get(field)
                    else None
                    for field in DATETIME_FIELDS
                },
            )
        except (AuthCredentialError, TypeError, ValueError):
            TokenStore.clear()
            return None

    @staticmethod
    def clear() -> None:
        flask.session.pop(TOKEN_SESSION_KEY, None)

    @staticmethod
    def exists() -> bool:
        return TOKEN_SESSION_KEY in flask.session
