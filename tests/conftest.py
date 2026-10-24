import flask
import pytest

from flask_githubkit import GitHubOAuth


@pytest.fixture
def github():
    return GitHubOAuth(scope="read:user repo", login_endpoint="login")


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
        return github.authorize()

    @app.route("/callback")
    @github.authorized_handler
    def callback(access_token):
        if access_token is None:
            return flask.jsonify({"message": "denied"}), 400
        return flask.jsonify({"message": "ok", "token": access_token})

    return app


@pytest.fixture
def client(app):
    return app.test_client()
