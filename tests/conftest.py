import flask
import pytest

import flask_githubkit


@pytest.fixture
def github():
    return flask_githubkit.GitHub(scope="read:user repo", login_view="login")


@pytest.fixture
def app(github):
    app = flask.Flask(__name__)
    app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret",
        GITHUB_CLIENT_ID="client-id",
        GITHUB_CLIENT_SECRET="client-secret",
        GITHUB_REDIRECT_URI="http://localhost:5000/callback",
    )
    github.init_app(app)

    @app.route("/login")
    def login():
        return github.login()

    @app.route("/callback")
    @github.callback
    def callback(access_token):
        if access_token is None:
            return flask.jsonify({"message": "denied"}), 400
        return flask.jsonify({"message": "ok", "token": access_token})

    return app


@pytest.fixture
def http_client(app):
    return app.test_client()
