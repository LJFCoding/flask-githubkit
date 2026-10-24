"""Everything flask_githubkit keeps in the Flask session."""

import datetime

import flask
import githubkit.auth
import githubkit.exception

import flask_githubkit.config

TOKEN_KEY = "flask_githubkit.token"
DATETIME_KEYS = ("expire_time", "refresh_token_expire_time")


class Token:
    """Keeps a user's GitHub tokens in ``flask.session``.

    With a server-side session backend such as Redis, the browser only
    holds the session id. Sessions are marked permanent, so
    ``PERMANENT_SESSION_LIFETIME`` is their expiry and each save resets
    it.
    """

    @staticmethod
    def save(strategy: githubkit.auth.OAuthTokenAuthStrategy) -> None:
        payload: dict[str, str | None] = {
            "token": strategy.token,
            "refresh_token": strategy.refresh_token,
        }
        for key in DATETIME_KEYS:
            value = getattr(strategy, key)
            payload[key] = value.isoformat() if value else None

        flask.session.permanent = True
        flask.session[TOKEN_KEY] = payload

    @staticmethod
    def load(
        config: flask_githubkit.config.Config,
    ) -> githubkit.auth.OAuthTokenAuthStrategy | None:
        payload = flask.session.get(TOKEN_KEY)
        if not isinstance(payload, dict):
            return None

        try:
            return githubkit.auth.OAuthTokenAuthStrategy(
                client_id=config.client_id,
                client_secret=config.client_secret,
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
            Token.clear()
            return None

    @staticmethod
    def clear() -> None:
        flask.session.pop(TOKEN_KEY, None)

    @staticmethod
    def exists() -> bool:
        return TOKEN_KEY in flask.session
