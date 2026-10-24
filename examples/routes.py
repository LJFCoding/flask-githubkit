"""Calling the GitHub API from a route with ``github.client()``.

``client()`` returns a GitHubKit client for the signed-in user, or
``None`` when nobody is signed in. Expired access tokens are refreshed
for you. If the refresh token has also expired, the user is sent to
the login view.

Run it with::

    export GITHUB_CLIENT_ID=... GITHUB_CLIENT_SECRET=... SECRET_KEY=...
    flask --app "examples/routes:create_app" run
"""

import collections.abc
import functools
import os
import typing

import flask

import flask_githubkit

github = flask_githubkit.GitHub()


def login_required(
    view: collections.abc.Callable[..., typing.Any],
) -> collections.abc.Callable[..., typing.Any]:
    @functools.wraps(view)
    def wrapper(*args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        if github.client() is None:
            return flask.redirect(flask.url_for("login"))
        return view(*args, **kwargs)

    return wrapper


def create_app() -> flask.Flask:
    app = flask.Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ["SECRET_KEY"],
        GITHUB_CLIENT_ID=os.environ["GITHUB_CLIENT_ID"],
        GITHUB_CLIENT_SECRET=os.environ["GITHUB_CLIENT_SECRET"],
        GITHUB_REDIRECT_URI="http://localhost:5000/callback",
    )
    github.init_app(app)

    @app.route("/login")
    def login():
        # The call form, for when you want to run code before redirecting.
        return github.login()

    @app.route("/callback")
    @github.callback
    def callback(access_token):
        if access_token is None:
            return "Access was denied.", 403
        return flask.redirect(flask.url_for("profile"))

    @app.route("/profile")
    @login_required
    def profile():
        user = github.client().rest.users.get_authenticated().parsed_data
        return flask.jsonify(login=user.login, name=user.name)

    @app.route("/logout")
    def logout():
        github.logout()
        return flask.redirect(flask.url_for("login"))

    return app
