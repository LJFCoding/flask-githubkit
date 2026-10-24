from dataclasses import dataclass

import flask


@dataclass(frozen=True)
class OAuthConfiguration:
    """OAuth App settings read from the Flask app config.

    Reads ``GITHUB_CLIENT_ID``, ``GITHUB_CLIENT_SECRET`` and
    ``GITHUB_REDIRECT_URI``. ``SECRET_KEY`` must also be set, because the OAuth
    state and tokens are kept in ``flask.session``.
    """

    client_id: str
    client_secret: str
    callback_url: str

    @staticmethod
    def from_app() -> "OAuthConfiguration | None":
        config = flask.current_app.config
        client_id = config.get("GITHUB_CLIENT_ID")
        client_secret = config.get("GITHUB_CLIENT_SECRET")
        callback_url = config.get("GITHUB_REDIRECT_URI")
        secret_key = config.get("SECRET_KEY")
        if not all(
            isinstance(value, str) and value
            for value in (client_id, client_secret, callback_url, secret_key)
        ):
            return None
        return OAuthConfiguration(str(client_id), str(client_secret), str(callback_url))
