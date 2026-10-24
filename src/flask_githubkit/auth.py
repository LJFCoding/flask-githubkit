"""GitHub OAuth web flow for Flask, backed by GitHubKit."""

import collections.abc
import functools
import hmac
import secrets
import typing
import urllib.parse

import flask
import githubkit
import githubkit.auth
import githubkit.exception
import werkzeug.wrappers

import flask_githubkit.config
import flask_githubkit.token

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
STATE_SESSION_KEY = "flask_githubkit.state"
G_CLIENT_ATTR = "github_client"

ViewResult = (
    werkzeug.wrappers.Response | tuple[werkzeug.wrappers.Response, int]
)


class GitHubOAuth:
    """GitHub OAuth web flow for Flask, backed by GitHubKit.

    ``authorize`` starts the flow and ``authorized_handler`` wraps the
    callback view, passing it the access token (or ``None`` if the user
    denied access). ``client`` returns one GitHub client per request for
    the signed-in user. ``init_app`` sends users to ``login_endpoint``
    when their refresh token has expired.

    ``scope`` is the space-separated OAuth scope to request. Tokens are
    kept by ``token.Store`` in ``flask.session``.
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
        self.store = flask_githubkit.token.Store()
        if app is not None:
            self.init_app(app)

    def init_app(self, app: flask.Flask) -> None:
        app.register_error_handler(
            githubkit.exception.AuthExpiredError, self._handle_auth_expired
        )

    def authorize(self) -> ViewResult:
        config = self._config()
        if config is None:
            return self._json_error("GitHub OAuth is not configured.", 500)

        state = secrets.token_urlsafe(32)
        flask.session[STATE_SESSION_KEY] = state

        query = urllib.parse.urlencode(
            {
                "client_id": config.client_id,
                "redirect_uri": config.redirect_uri,
                "scope": self.scope,
                "state": state,
            }
        )
        return flask.redirect(f"{GITHUB_AUTHORIZE_URL}?{query}")

    def authorized_handler(
        self, view_func: collections.abc.Callable[..., ViewResult]
    ) -> collections.abc.Callable[..., ViewResult]:
        @functools.wraps(view_func)
        def decorated(*args: typing.Any, **kwargs: typing.Any) -> ViewResult:
            if not self._consume_state():
                return self._json_error("Invalid OAuth state.", 400)

            if flask.request.args.get("error"):
                return view_func(None, *args, **kwargs)

            auth_code = flask.request.args.get("code")
            if not auth_code:
                return self._json_error(
                    "GitHub did not return an authorization code.", 400
                )

            config = self._config()
            if config is None:
                return self._json_error("GitHub OAuth is not configured.", 500)

            strategy = self._exchange_code(auth_code, config)
            self.store.save(strategy)
            return view_func(strategy.token, *args, **kwargs)

        return decorated

    def client(self) -> "githubkit.GitHub[typing.Any] | None":
        """Return the request's GitHub client, or None if signed out.

        The client is created once per request, so a token refresh
        happens once and every caller sees the new token. GitHubKit
        refreshes an expired access token itself; the refreshed values
        are saved to the session at the end of the request.
        """
        cached: githubkit.GitHub[typing.Any] | None = getattr(
            flask.g, G_CLIENT_ATTR, None
        )
        if cached is not None:
            return cached

        config = self._config()
        if config is None:
            return None
        strategy = self.store.load(config)
        if strategy is None:
            return None

        def _save_refreshed_token(
            response: werkzeug.wrappers.Response,
        ) -> werkzeug.wrappers.Response:
            if self.store.has_token():
                self.store.save(strategy)
            return response

        flask.after_this_request(_save_refreshed_token)
        github = githubkit.GitHub(auth=strategy)
        setattr(flask.g, G_CLIENT_ATTR, github)
        return github

    def logout(self) -> None:
        self.store.clear()

    @staticmethod
    def _config() -> flask_githubkit.config.Config | None:
        return flask_githubkit.config.Config.from_current_app()

    @staticmethod
    def _consume_state() -> bool:
        expected = flask.session.pop(STATE_SESSION_KEY, None)
        received = flask.request.args.get("state", "")
        return isinstance(expected, str) and hmac.compare_digest(
            expected, received
        )

    @staticmethod
    def _exchange_code(
        auth_code: str,
        config: flask_githubkit.config.Config,
    ) -> githubkit.auth.OAuthTokenAuthStrategy:
        oauth_app = githubkit.auth.OAuthAppAuthStrategy(
            client_id=config.client_id,
            client_secret=config.client_secret,
        )
        return oauth_app.as_web_user(
            auth_code, redirect_uri=config.redirect_uri
        ).exchange_token(githubkit.GitHub(auth=oauth_app))

    def _handle_auth_expired(
        self, error: githubkit.exception.AuthExpiredError
    ) -> werkzeug.wrappers.Response:
        self.logout()
        return flask.redirect(flask.url_for(self.login_endpoint))

    @staticmethod
    def _json_error(
        message: str, status: int
    ) -> tuple[werkzeug.wrappers.Response, int]:
        return flask.jsonify({"message": message}), status
