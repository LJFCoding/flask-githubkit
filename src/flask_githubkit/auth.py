import flask
from githubkit.exception import AuthExpiredError
from werkzeug.wrappers import Response

from .token_store import TokenStore


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

    def logout(self) -> None:
        self.store.clear()

    def _handle_expired(self, error: AuthExpiredError) -> Response:
        self.logout()
        return flask.redirect(flask.url_for(self.login_endpoint))
