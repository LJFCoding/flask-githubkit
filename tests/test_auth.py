from urllib.parse import parse_qs, urlparse

import flask
from githubkit.exception import AuthExpiredError

from flask_githubkit import auth as auth_module

TOKEN = {
    "token": "token",
    "refresh_token": None,
    "expire_time": None,
    "refresh_token_expire_time": None,
}


def test_login_redirects_to_github_with_state_scope_and_callback(client):
    response = client.get("/login")

    assert response.status_code == 302
    redirect = urlparse(response.headers["Location"])
    query = parse_qs(redirect.query)
    assert (redirect.scheme, redirect.netloc, redirect.path) == (
        "https",
        "github.com",
        "/login/oauth/authorize",
    )
    assert query["client_id"] == ["client-id"]
    assert query["redirect_uri"] == ["http://localhost:5000/callback"]
    assert query["scope"] == ["read:user repo"]
    assert len(query["state"][0]) >= 32
    with client.session_transaction() as session:
        assert session["flask_githubkit.state"] == query["state"][0]


def test_login_reports_missing_configuration(app, client):
    app.config["GITHUB_CLIENT_ID"] = None

    response = client.get("/login")

    assert response.status_code == 500
    assert response.get_json() == {"message": "GitHub OAuth is not configured."}


def test_callback_rejects_invalid_state(client):
    response = client.get("/callback?state=wrong&code=example")

    assert response.status_code == 400
    assert response.get_json() == {"message": "Invalid OAuth state."}


def test_callback_passes_none_when_access_is_denied(client):
    with client.session_transaction() as session:
        session["flask_githubkit.state"] = "expected"

    response = client.get("/callback?state=expected&error=access_denied")

    assert response.status_code == 400
    assert response.get_json() == {"message": "denied"}


def test_callback_requires_a_code(client):
    with client.session_transaction() as session:
        session["flask_githubkit.state"] = "expected"

    response = client.get("/callback?state=expected")

    assert response.status_code == 400
    assert response.get_json() == {
        "message": "GitHub did not return an authorization code."
    }


def test_callback_exchanges_code_and_stores_tokens(client, monkeypatch):
    with client.session_transaction() as session:
        session["flask_githubkit.state"] = "expected"
    calls = {}

    class FakeWebAuth:
        def exchange_token(self, github):
            calls["github"] = github
            return type(
                "FakeToken",
                (),
                {
                    "token": "access-token",
                    "refresh_token": "refresh-token",
                    "expire_time": None,
                    "refresh_token_expire_time": None,
                },
            )()

    class FakeOAuthApp:
        def __init__(self, *, client_id, client_secret):
            calls["credentials"] = (client_id, client_secret)

        def as_web_user(self, code, *, redirect_uri):
            calls["web_auth"] = (code, redirect_uri)
            return FakeWebAuth()

    class FakeGitHub:
        def __init__(self, *, auth):
            self.auth = auth

    monkeypatch.setattr(auth_module, "OAuthAppAuthStrategy", FakeOAuthApp)
    monkeypatch.setattr(auth_module, "GitHub", FakeGitHub)

    response = client.get("/callback?state=expected&code=oauth-code")

    assert response.get_json() == {"message": "ok", "token": "access-token"}
    assert calls["credentials"] == ("client-id", "client-secret")
    assert calls["web_auth"] == ("oauth-code", "http://localhost:5000/callback")
    assert isinstance(calls["github"].auth, FakeOAuthApp)
    with client.session_transaction() as session:
        assert session["flask_githubkit.token"]["token"] == "access-token"
        assert session["flask_githubkit.token"]["refresh_token"] == "refresh-token"
        assert session.permanent


def test_client_is_none_when_signed_out(app, github):
    with app.test_request_context():
        assert github.client() is None


def test_client_is_cached_per_request(app, github):
    with app.test_request_context():
        flask.session["flask_githubkit.token"] = TOKEN

        assert github.client() is github.client()


def test_invalid_stored_token_is_cleared(app, github):
    with app.test_request_context():
        flask.session["flask_githubkit.token"] = {"token": None, "refresh_token": None}

        assert github.client() is None
        assert "flask_githubkit.token" not in flask.session


def test_refreshed_token_is_written_back_to_session(app, github, client):
    @app.route("/refresh")
    def refresh():
        api = github.client()
        # Stand-in for GitHubKit refreshing the token in place during a call.
        api.auth.token = "new-token"
        api.auth.refresh_token = "new-refresh"
        return flask.jsonify({})

    with client.session_transaction() as session:
        session["flask_githubkit.token"] = {
            "token": "old-token",
            "refresh_token": "old-refresh",
            "expire_time": "2020-01-01T00:00:00+00:00",
            "refresh_token_expire_time": "2099-01-01T00:00:00+00:00",
        }

    assert client.get("/refresh").status_code == 200
    with client.session_transaction() as session:
        assert session["flask_githubkit.token"]["token"] == "new-token"
        assert session["flask_githubkit.token"]["refresh_token"] == "new-refresh"


def test_logout_removes_stored_token(app, github):
    with app.test_request_context():
        flask.session["flask_githubkit.token"] = TOKEN

        github.logout()

        assert "flask_githubkit.token" not in flask.session


def test_expired_refresh_token_clears_session_and_redirects_to_login(app, client):
    @app.route("/expired")
    def expired():
        raise AuthExpiredError("Refresh token expired.")

    with client.session_transaction() as session:
        session["flask_githubkit.token"] = TOKEN

    response = client.get("/expired")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with client.session_transaction() as session:
        assert "flask_githubkit.token" not in session
