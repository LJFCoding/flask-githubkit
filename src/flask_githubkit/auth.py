"""GitHub OAuth web flow for Flask, backed by GitHubKit."""

import collections.abc
import functools
import typing
import urllib.parse

import flask
import githubkit
import githubkit.auth
import githubkit.exception
import httpx
import werkzeug.routing
import werkzeug.wrappers

import flask_githubkit.config
import flask_githubkit.store

AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
CLIENT_ATTR = "flask_githubkit_client"
LOGIN_VIEW = "login"

ViewResult = (
    werkzeug.wrappers.Response | tuple[werkzeug.wrappers.Response, int]
)


class GitHub:
    """GitHub OAuth web flow for Flask, backed by GitHubKit.

    ``login`` starts the flow and ``callback`` wraps the callback view,
    passing it the access token (or ``None`` if the user denied
    access). ``client`` returns one GitHub client per request for the
    signed-in user. ``init_app`` sends users to the endpoint named by
    ``GITHUB_LOGIN_VIEW`` (default ``login``) when their refresh token
    has expired.

    ``scope`` and ``login_view`` may be given here. When they are not,
    they come from ``GITHUB_SCOPE`` and ``GITHUB_LOGIN_VIEW`` in the
    Flask config, and then from the defaults (``read:user`` and
    ``login``). Tokens are kept by ``store.Token`` in ``flask.session``.
    """

    def __init__(
        self,
        app: flask.Flask | None = None,
        *,
        scope: str | None = None,
        login_view: str | None = None,
    ) -> None:
        self.scope = scope
        self.login_view = login_view
        if app is not None:
            self.init_app(app)

    def init_app(self, app: flask.Flask) -> None:
        app.register_error_handler(
            githubkit.exception.AuthExpiredError, self._expired
        )

    @typing.overload
    def login(self) -> ViewResult: ...

    @typing.overload
    def login(
        self, view_func: collections.abc.Callable[..., typing.Any]
    ) -> collections.abc.Callable[..., ViewResult]: ...

    def login(
        self,
        view_func: collections.abc.Callable[..., typing.Any] | None = None,
    ) -> ViewResult | collections.abc.Callable[..., ViewResult]:
        """Start the OAuth flow.

        Call ``login()`` inside a view, or use ``@github.login`` as a
        decorator. The decorated function is replaced by one that
        redirects to GitHub, and keeps its name for ``url_for``.
        """
        if view_func is None:
            return self._redirect()

        @functools.wraps(view_func)
        def wrapper(*args: typing.Any, **kwargs: typing.Any) -> ViewResult:
            return self._redirect()

        return wrapper

    def _redirect(self) -> ViewResult:
        config = self._config()
        if config is None:
            return self._error("GitHub OAuth is not configured.", 500)
        return flask.redirect(self._url(config))

    def callback(
        self, view_func: collections.abc.Callable[..., ViewResult]
    ) -> collections.abc.Callable[..., ViewResult]:
        @functools.wraps(view_func)
        def wrapper(*args: typing.Any, **kwargs: typing.Any) -> ViewResult:
            if not self._check_state():
                return self._error("Invalid OAuth state.", 400)

            if flask.request.args.get("error"):
                return view_func(None, *args, **kwargs)

            code = flask.request.args.get("code")
            if not code:
                return self._error(
                    "GitHub did not return an authorization code.", 400
                )

            config = self._config()
            if config is None:
                return self._error("GitHub OAuth is not configured.", 500)

            try:
                strategy = self._exchange(code, config)
            except (githubkit.exception.RequestError, httpx.HTTPError):
                return self._error("Could not reach GitHub.", 502)
            flask_githubkit.store.Token.save(strategy)
            return view_func(strategy.token, *args, **kwargs)

        return wrapper

    def client(self) -> "githubkit.GitHub[typing.Any] | None":
        """Return the request's GitHub client, or None if signed out.

        The client is created once per request, so a token refresh
        happens once and every caller sees the new token. GitHubKit
        refreshes an expired access token itself; the refreshed values
        are saved to the session at the end of the request.
        """
        cached: githubkit.GitHub[typing.Any] | None = getattr(
            flask.g, CLIENT_ATTR, None
        )
        if cached is not None:
            return cached

        config = self._config()
        if config is None:
            return None
        strategy = flask_githubkit.store.Token.load(config)
        if strategy is None:
            return None

        def _save(
            response: werkzeug.wrappers.Response,
        ) -> werkzeug.wrappers.Response:
            if flask_githubkit.store.Token.exists():
                flask_githubkit.store.Token.save(strategy)
            return response

        flask.after_this_request(_save)
        github = githubkit.GitHub(auth=strategy)
        setattr(flask.g, CLIENT_ATTR, github)
        return github

    def logout(self) -> None:
        flask_githubkit.store.Token.clear()

    @staticmethod
    def _config() -> flask_githubkit.config.Config | None:
        return flask_githubkit.config.Config.from_current_app()

    def _url(self, config: flask_githubkit.config.Config) -> str:
        query = urllib.parse.urlencode(
            {
                "client_id": config.client_id,
                "redirect_uri": config.redirect_uri,
                "scope": self.scope or config.scope,
                "state": flask_githubkit.store.State.new(),
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    @staticmethod
    def _check_state() -> bool:
        received = flask.request.args.get("state", "")
        return flask_githubkit.store.State.check(received)

    @staticmethod
    def _exchange(
        code: str,
        config: flask_githubkit.config.Config,
    ) -> githubkit.auth.OAuthTokenAuthStrategy:
        app = githubkit.auth.OAuthAppAuthStrategy(
            client_id=config.client_id,
            client_secret=config.client_secret,
        )
        return app.as_web_user(
            code, redirect_uri=config.redirect_uri
        ).exchange_token(githubkit.GitHub(auth=app))

    def _expired(
        self, error: githubkit.exception.AuthExpiredError
    ) -> werkzeug.wrappers.Response:
        self.logout()
        view = self.login_view or flask.current_app.config.get(
            "GITHUB_LOGIN_VIEW", LOGIN_VIEW
        )
        try:
            return flask.redirect(flask.url_for(view))
        except werkzeug.routing.BuildError as build_error:
            raise RuntimeError(
                f"GITHUB_LOGIN_VIEW {view!r} is not a Flask endpoint. "
                "Use the endpoint name, such as 'auth.login' for a "
                "blueprint named 'auth'."
            ) from build_error

    @staticmethod
    def _error(
        message: str, status: int
    ) -> tuple[werkzeug.wrappers.Response, int]:
        return flask.jsonify({"message": message}), status
