from datetime import datetime

import flask
from githubkit.auth import OAuthTokenAuthStrategy
from githubkit.exception import AuthCredentialError

from .configuration import OAuthConfiguration

TOKEN_SESSION_KEY = "flask_githubkit.token"
DATETIME_KEYS = ("expire_time", "refresh_token_expire_time")


class TokenStore:
    """Keeps a user's GitHub tokens in ``flask.session``.

    With a server-side session backend such as Redis, the browser only holds
    the session id. Sessions are marked permanent, so
    ``PERMANENT_SESSION_LIFETIME`` is their expiry and each save resets it.
    """

    @staticmethod
    def save(token_auth: OAuthTokenAuthStrategy) -> None:
        payload: dict[str, str | None] = {
            "token": token_auth.token,
            "refresh_token": token_auth.refresh_token,
        }
        for field in DATETIME_KEYS:
            value = getattr(token_auth, field)
            payload[field] = value.isoformat() if value else None

        flask.session.permanent = True
        if flask.session.get(TOKEN_SESSION_KEY) != payload:
            flask.session[TOKEN_SESSION_KEY] = payload

    @staticmethod
    def load(
        configuration: OAuthConfiguration,
    ) -> OAuthTokenAuthStrategy | None:
        payload = flask.session.get(TOKEN_SESSION_KEY)
        if not isinstance(payload, dict):
            return None

        try:
            return OAuthTokenAuthStrategy(
                client_id=configuration.client_id,
                client_secret=configuration.client_secret,
                token=payload.get("token"),
                refresh_token=payload.get("refresh_token"),
                **{
                    field: datetime.fromisoformat(payload[field])
                    if payload.get(field)
                    else None
                    for field in DATETIME_KEYS
                },
            )
        except (AuthCredentialError, TypeError, ValueError):
            TokenStore.clear()
            return None

    @staticmethod
    def clear() -> None:
        flask.session.pop(TOKEN_SESSION_KEY, None)

    @staticmethod
    def has_token() -> bool:
        return TOKEN_SESSION_KEY in flask.session
