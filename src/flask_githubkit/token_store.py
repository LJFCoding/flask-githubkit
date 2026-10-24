"""Store a user's GitHub tokens in the Flask session."""

import datetime

import flask
import githubkit.auth
import githubkit.exception

import flask_githubkit.configuration

TOKEN_SESSION_KEY = "flask_githubkit.token"
DATETIME_KEYS = ("expire_time", "refresh_token_expire_time")


class TokenStore:
    """Keeps a user's GitHub tokens in ``flask.session``.

    With a server-side session backend such as Redis, the browser only
    holds the session id. Sessions are marked permanent, so
    ``PERMANENT_SESSION_LIFETIME`` is their expiry and each save resets
    it.
    """

    @staticmethod
    def save(token_strategy: githubkit.auth.OAuthTokenAuthStrategy) -> None:
        payload: dict[str, str | None] = {
            "token": token_strategy.token,
            "refresh_token": token_strategy.refresh_token,
        }
        for key in DATETIME_KEYS:
            value = getattr(token_strategy, key)
            payload[key] = value.isoformat() if value else None

        flask.session.permanent = True
        if flask.session.get(TOKEN_SESSION_KEY) != payload:
            flask.session[TOKEN_SESSION_KEY] = payload

    @staticmethod
    def load(
        oauth_config: flask_githubkit.configuration.OAuthConfiguration,
    ) -> githubkit.auth.OAuthTokenAuthStrategy | None:
        payload = flask.session.get(TOKEN_SESSION_KEY)
        if not isinstance(payload, dict):
            return None

        try:
            return githubkit.auth.OAuthTokenAuthStrategy(
                client_id=oauth_config.client_id,
                client_secret=oauth_config.client_secret,
                token=payload.get("token"),
                refresh_token=payload.get("refresh_token"),
                **{
                    key: datetime.datetime.fromisoformat(payload[key])
                    if payload.get(key)
                    else None
                    for key in DATETIME_KEYS
                },
            )
        except (
            githubkit.exception.AuthCredentialError,
            TypeError,
            ValueError,
        ):
            TokenStore.clear()
            return None

    @staticmethod
    def clear() -> None:
        flask.session.pop(TOKEN_SESSION_KEY, None)

    @staticmethod
    def has_token() -> bool:
        return TOKEN_SESSION_KEY in flask.session
