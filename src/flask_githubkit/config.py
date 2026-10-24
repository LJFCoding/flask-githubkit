"""OAuth App settings read from the Flask application config."""

import dataclasses

import flask

SCOPE = "read:user"


@dataclasses.dataclass(frozen=True)
class Config:
    """OAuth App settings read from the Flask app config.

    Reads ``GITHUB_CLIENT_ID``, ``GITHUB_CLIENT_SECRET`` and
    ``GITHUB_REDIRECT_URI``. ``SECRET_KEY`` must also be set, because
    the OAuth state and tokens are kept in ``flask.session``.
    ``GITHUB_SCOPE`` is optional: the space-separated OAuth scope to
    request, ``read:user`` by default.
    """

    client_id: str
    client_secret: str
    redirect_uri: str
    scope: str = SCOPE

    @staticmethod
    def from_current_app() -> "Config | None":
        app_config = flask.current_app.config
        client_id = app_config.get("GITHUB_CLIENT_ID")
        client_secret = app_config.get("GITHUB_CLIENT_SECRET")
        redirect_uri = app_config.get("GITHUB_REDIRECT_URI")
        scope = app_config.get("GITHUB_SCOPE", SCOPE)
        secret_key = app_config.get("SECRET_KEY")
        if not all(
            isinstance(value, str) and value
            for value in (
                client_id,
                client_secret,
                redirect_uri,
                scope,
                secret_key,
            )
        ):
            return None
        return Config(
            str(client_id), str(client_secret), str(redirect_uri), str(scope)
        )
