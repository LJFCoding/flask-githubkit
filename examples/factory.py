"""App factory: create the extension once, attach it in ``create_app``.

Run it with::

    export GITHUB_CLIENT_ID=... GITHUB_CLIENT_SECRET=... SECRET_KEY=...
    flask --app "examples/factory:create_app" run
"""

import os

import flask

import flask_githubkit

# Normally this lives in extensions.py so any module can import it.
github = flask_githubkit.GitHub()


def create_app() -> flask.Flask:
    app = flask.Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ["SECRET_KEY"],
        GITHUB_CLIENT_ID=os.environ["GITHUB_CLIENT_ID"],
        GITHUB_CLIENT_SECRET=os.environ["GITHUB_CLIENT_SECRET"],
        GITHUB_REDIRECT_URI="http://localhost:5000/callback",
        # Optional. Both can also be passed to GitHub(...).
        GITHUB_SCOPE="read:user user:email",
        GITHUB_LOGIN_VIEW="login",
    )
    github.init_app(app)

    @app.route("/login")
    def login():
        return github.login()

    @app.route("/callback")
    @github.callback
    def callback(access_token):
        if access_token is None:
            return "Access was denied.", 403
        return flask.redirect("/")

    @app.route("/")
    def index():
        return '<a href="/login">Sign in with GitHub</a>'

    return app
