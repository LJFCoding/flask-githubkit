"""The smallest app: one file, module-level ``app``.

Run it with::

    export GITHUB_CLIENT_ID=... GITHUB_CLIENT_SECRET=... SECRET_KEY=...
    flask --app examples/single_file run
"""

import os

import flask

import flask_githubkit

app = flask.Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ["SECRET_KEY"],
    GITHUB_CLIENT_ID=os.environ["GITHUB_CLIENT_ID"],
    GITHUB_CLIENT_SECRET=os.environ["GITHUB_CLIENT_SECRET"],
    GITHUB_REDIRECT_URI="http://localhost:5000/callback",
)
github = flask_githubkit.GitHub(app)


@app.route("/")
def index():
    return '<a href="/login">Sign in with GitHub</a>'


@app.route("/login")
@github.login
def login():
    """Replaced by a redirect to GitHub."""


@app.route("/callback")
@github.callback
def callback(access_token):
    if access_token is None:
        return "Access was denied.", 403
    return flask.redirect("/")
