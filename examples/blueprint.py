"""Blueprint: login and callback live under ``/auth``.

``@github.login`` marks the view, so after an expired refresh token the
user is sent to ``auth.login`` without any ``login_view`` setting. The
callback URL registered in your OAuth App must be
``http://localhost:5000/auth/callback``.

Run it with::

    export GITHUB_CLIENT_ID=... GITHUB_CLIENT_SECRET=... SECRET_KEY=...
    flask --app "examples/blueprint:create_app" run
"""

import os

import flask

import flask_githubkit

github = flask_githubkit.GitHub()

auth = flask.Blueprint("auth", __name__, url_prefix="/auth")


@auth.route("/login")
@github.login
def login():
    """Replaced by a redirect to GitHub."""


@auth.route("/callback")
@github.callback
def callback(access_token):
    if access_token is None:
        return "Access was denied.", 403
    return flask.redirect("/")


@auth.route("/logout")
def logout():
    github.logout()
    return flask.redirect("/")


def create_app() -> flask.Flask:
    app = flask.Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ["SECRET_KEY"],
        GITHUB_CLIENT_ID=os.environ["GITHUB_CLIENT_ID"],
        GITHUB_CLIENT_SECRET=os.environ["GITHUB_CLIENT_SECRET"],
    )
    github.init_app(app)
    app.register_blueprint(auth)
    return app
