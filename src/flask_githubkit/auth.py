import hmac
import secrets
from collections.abc import Callable
from functools import wraps
from typing import Any
from urllib.parse import urlencode

import flask
from githubkit import GitHub
from githubkit.auth import OAuthAppAuthStrategy, OAuthTokenAuthStrategy
from githubkit.exception import AuthExpiredError
from werkzeug.wrappers import Response

from .configuration import OAuthConfiguration
from .token_store import TokenStore

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
STATE_SESSION_KEY = "flask_githubkit.state"
G_CLIENT_ATTR = "github_client"

ViewResult = Response | tuple[Response, int]


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
        self.token_store = TokenStore()
        if app is not None:
            self.init_app(app)

    def init_app(self, app: flask.Flask) -> None:
        app.register_error_handler(AuthExpiredError, self._handle_auth_expired)

    def authorize(self) -> ViewResult:
        oauth_config = OAuthConfiguration.from_current_app()
        if oauth_config is None:
            return self._json_error("GitHub OAuth is not configured.", 500)

        state = secrets.token_urlsafe(32)
        flask.session[STATE_SESSION_KEY] = state

        query = urlencode(
            {
                "client_id": oauth_config.client_id,
                "redirect_uri": oauth_config.redirect_uri,
                "scope": self.scope,
                "state": state,
            }
        )
        return flask.redirect(f"{GITHUB_AUTHORIZE_URL}?{query}")

    def authorized_handler(
        self, view_func: Callable[..., ViewResult]
    ) -> Callable[..., ViewResult]:
        @wraps(view_func)
        def decorated(*args: Any, **kwargs: Any) -> ViewResult:
            if not self._consume_state():
                return self._json_error("Invalid OAuth state.", 400)

            if flask.request.args.get("error"):
                return view_func(None, *args, **kwargs)

            auth_code = flask.request.args.get("code")
            if not auth_code:
                return self._json_error(
                    "GitHub did not return an authorization code.", 400
                )

            oauth_config = OAuthConfiguration.from_current_app()
            if oauth_config is None:
                return self._json_error("GitHub OAuth is not configured.", 500)

            token_strategy = self._exchange_code(auth_code, oauth_config)
            self.token_store.save(token_strategy)
            return view_func(token_strategy.token, *args, **kwargs)

        return decorated

    def client(self) -> "GitHub[Any] | None":
        """Return the request's GitHub client, or None if signed out.

        The client is created once per request, so a token refresh happens once
        and every caller sees the new token. GitHubKit refreshes an expired
        access token itself; the refreshed values are saved to the session at
        the end of the request.
        """
        cached: GitHub[Any] | None = getattr(flask.g, G_CLIENT_ATTR, None)
        if cached is not None:
            return cached

        oauth_config = OAuthConfiguration.from_current_app()
        if oauth_config is None:
            return None
        token_strategy = self.token_store.load(oauth_config)
        if token_strategy is None:
            return None

        def _save_refreshed_token(response: Response) -> Response:
            if self.token_store.has_token():
                self.token_store.save(token_strategy)
            return response

        flask.after_this_request(_save_refreshed_token)
        github = GitHub(auth=token_strategy)
        setattr(flask.g, G_CLIENT_ATTR, github)
        return github

    def logout(self) -> None:
        self.token_store.clear()

    @staticmethod
    def _consume_state() -> bool:
        expected = flask.session.pop(STATE_SESSION_KEY, None)
        received = flask.request.args.get("state", "")
        return isinstance(expected, str) and hmac.compare_digest(expected, received)

    @staticmethod
    def _exchange_code(
        auth_code: str, oauth_config: OAuthConfiguration
    ) -> OAuthTokenAuthStrategy:
        oauth_app = OAuthAppAuthStrategy(
            client_id=oauth_config.client_id,
            client_secret=oauth_config.client_secret,
        )
        return oauth_app.as_web_user(
            auth_code, redirect_uri=oauth_config.redirect_uri
        ).exchange_token(GitHub(auth=oauth_app))

    def _handle_auth_expired(self, error: AuthExpiredError) -> Response:
        self.logout()
        return flask.redirect(flask.url_for(self.login_endpoint))

    @staticmethod
    def _json_error(message: str, status: int) -> tuple[Response, int]:
        return flask.jsonify({"message": message}), status
