import flask
import pytest

from flask_githubkit import GitHubOAuth


@pytest.fixture
def oauth():
    return GitHubOAuth(scope="read:user repo", login_endpoint="login")


@pytest.fixture
def app(oauth):
    app = flask.Flask(__name__)
    app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret",
        GITHUB_CLIENT_ID="client-id",
        GITHUB_CLIENT_SECRET="client-secret",
        GITHUB_REDIRECT_URI="http://localhost:5000/callback",
    )
    oauth.init_app(app)

    @app.route("/login")
    def login():
        return oauth.authorize()

    @app.route("/callback")
    @oauth.authorized_handler
    def callback(access_token):
        if access_token is None:
            return flask.jsonify({"message": "denied"}), 400
        return flask.jsonify({"message": "ok", "token": access_token})

    return app


@pytest.fixture
def http_client(app):
    return app.test_client()
