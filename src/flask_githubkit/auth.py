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
LOGIN_MARK = "_flask_githubkit_login"
CALLBACK_MARK = "_flask_githubkit_callback"
CALLBACK_VIEW_KEY = "GITHUB_CALLBACK_VIEW"

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
    Flask config. The scope then defaults to ``read:user``. The login
    view defaults to the view decorated with ``@login``, or to
    ``login`` if there is none. Tokens are kept by ``store.Token`` in
    ``flask.session``.
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
        """Register the ``AuthExpiredError`` handler on ``app``."""
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

        setattr(wrapper, LOGIN_MARK, self)
        return wrapper

    def _redirect(self) -> ViewResult:
        config = self._config()
        if config is None:
            return self._error("GitHub OAuth is not configured.", 500)
        return flask.redirect(self._url(config))

    def callback(
        self, view_func: collections.abc.Callable[..., ViewResult]
    ) -> collections.abc.Callable[..., ViewResult]:
        """Wrap the callback view.

        The wrapper checks the OAuth ``state``, exchanges the code and
        saves the token. It then calls the view with the access token,
        or with ``None`` if the user denied access.
        """

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

        setattr(wrapper, CALLBACK_MARK, self)
        return wrapper

    def client(self) -> "githubkit.GitHub[typing.Any] | None":
        """Return the request's GitHub client, or None if signed out.

        The client is created once per request, so a token refresh
        happens once and every caller sees the new token. GitHubKit
        refreshes an expired access token itself; the refreshed values
        are saved to the session at the end of the request.
        """
        clients: dict[GitHub, githubkit.GitHub[typing.Any]] | None = getattr(
            flask.g, CLIENT_ATTR, None
        )
        if clients is None:
            clients = {}
            setattr(flask.g, CLIENT_ATTR, clients)

        cached = clients.get(self)
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
        clients[self] = github
        return github

    def logout(self) -> None:
        """Remove the stored token and any cached client."""
        flask_githubkit.store.Token.clear()
        flask.g.pop(CLIENT_ATTR, None)

    @staticmethod
    def _config() -> flask_githubkit.config.Config | None:
        return flask_githubkit.config.Config.from_current_app()

    def _url(self, config: flask_githubkit.config.Config) -> str:
        query = urllib.parse.urlencode(
            {
                "client_id": config.client_id,
                "redirect_uri": self._redirect_uri(config),
                "scope": self.scope or config.scope,
                "state": flask_githubkit.store.State.new(),
            }
        )
        return f"{AUTHORIZE_URL}?{query}"

    def _redirect_uri(self, config: flask_githubkit.config.Config) -> str:
        """Return ``GITHUB_REDIRECT_URI``, or the ``@callback`` view's URL."""
        if config.redirect_uri:
            return config.redirect_uri
        app_config = flask.current_app.config
        endpoint = app_config.get(CALLBACK_VIEW_KEY)
        if endpoint is None:
            endpoint = self._decorated_endpoint(CALLBACK_MARK)
            if endpoint is None:
                raise RuntimeError(
                    "No callback URL. Decorate the callback view with "
                    "@github.callback or set GITHUB_REDIRECT_URI."
                )
            app_config[CALLBACK_VIEW_KEY] = endpoint
        return flask.url_for(endpoint, _external=True)

    @staticmethod
    def _check_state() -> bool:
        received = flask.request.args.get("state", "")
        return flask_githubkit.store.State.check(received)

    def _exchange(
        self,
        code: str,
        config: flask_githubkit.config.Config,
    ) -> githubkit.auth.OAuthTokenAuthStrategy:
        app = githubkit.auth.OAuthAppAuthStrategy(
            client_id=config.client_id,
            client_secret=config.client_secret,
        )
        return app.as_web_user(
            code, redirect_uri=self._redirect_uri(config)
        ).exchange_token(githubkit.GitHub(auth=app))

    def _expired(
        self, error: githubkit.exception.AuthExpiredError
    ) -> werkzeug.wrappers.Response:
        self.logout()
        view = (
            self.login_view
            or flask.current_app.config.get("GITHUB_LOGIN_VIEW")
            or self._decorated_endpoint()
            or LOGIN_VIEW
        )
        try:
            return flask.redirect(flask.url_for(view))
        except werkzeug.routing.BuildError as build_error:
            raise RuntimeError(
                f"GITHUB_LOGIN_VIEW {view!r} is not a Flask endpoint. "
                "Use the endpoint name, such as 'auth.login' for a "
                "blueprint named 'auth'."
            ) from build_error

    def _decorated_endpoint(self, mark: str = LOGIN_MARK) -> str | None:
        """Return the endpoint of the view tagged with ``mark``."""
        for endpoint, view in flask.current_app.view_functions.items():
            if getattr(view, mark, None) is self:
                return endpoint
        return None

    @staticmethod
    def _error(
        message: str, status: int
    ) -> tuple[werkzeug.wrappers.Response, int]:
        return flask.jsonify({"message": message}), status
