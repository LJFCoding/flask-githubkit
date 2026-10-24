import secrets
from urllib.parse import urlencode

import flask
from githubkit.exception import AuthExpiredError
from werkzeug.wrappers import Response

from .configuration import OAuthConfiguration
from .token_store import TokenStore

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
STATE_SESSION_KEY = "github_oauth_state"

Result = Response | tuple[Response, int]


class GitHubOAuth:
    """GitHub OAuth web flow for Flask, backed by GitHubKit.

    ``authorize`` starts the flow and ``authorized_handler`` wraps the callback
    view, passing it the access token (or ``None`` if the user denied access).
    ``client`` returns one GitHub client per request for the signed-in user.
    ``init_app`` sends users to ``login_endpoint`` when their refresh token has
    expired.

    ``scope`` is the space-separated OAuth scope to request. Tokens are kept by
    ``TokenStore`` in ``flask.session``.
    """

    def __init__(
        self,
        app: flask.Flask | None = None,
        *,
        scope: str = "read:user",
        login_endpoint: str = "login",
    ) -> None:
        self.scope = scope
        self.login_endpoint = login_endpoint
        self.store = TokenStore()
        if app is not None:
            self.init_app(app)

    def init_app(self, app: flask.Flask) -> None:
        app.register_error_handler(AuthExpiredError, self._handle_expired)

    def authorize(self) -> Result:
        configuration = OAuthConfiguration.from_app()
        if configuration is None:
            return self._error("GitHub OAuth is not configured.", 500)

        state = secrets.token_urlsafe(32)
        flask.session[STATE_SESSION_KEY] = state

        query = urlencode(
            {
                "client_id": configuration.client_id,
                "redirect_uri": configuration.callback_url,
                "scope": self.scope,
                "state": state,
            }
        )
        return flask.redirect(f"{AUTHORIZE_URL}?{query}")

    def logout(self) -> None:
        self.store.clear()

    def _handle_expired(self, error: AuthExpiredError) -> Response:
        self.logout()
        return flask.redirect(flask.url_for(self.login_endpoint))

    @staticmethod
    def _error(message: str, status: int) -> tuple[Response, int]:
        return flask.jsonify({"message": message}), status
