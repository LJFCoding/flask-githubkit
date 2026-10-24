from urllib.parse import parse_qs, urlparse

import flask
from githubkit.exception import AuthExpiredError

from flask_githubkit import auth as auth_module

SAMPLE_TOKEN = {
    "token": "token",
    "refresh_token": None,
    "expire_time": None,
    "refresh_token_expire_time": None,
}


def test_login_redirects_to_github_with_state_scope_and_callback(http_client):
    response = http_client.get("/login")

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
    with http_client.session_transaction() as session:
        assert session["flask_githubkit.state"] == query["state"][0]


def test_login_reports_missing_configuration(app, http_client):
    app.config["GITHUB_CLIENT_ID"] = None

    response = http_client.get("/login")

    assert response.status_code == 500
    assert response.get_json() == {"message": "GitHub OAuth is not configured."}


def test_callback_rejects_invalid_state(http_client):
    response = http_client.get("/callback?state=wrong&code=example")

    assert response.status_code == 400
    assert response.get_json() == {"message": "Invalid OAuth state."}


def test_callback_passes_none_when_access_is_denied(http_client):
    with http_client.session_transaction() as session:
        session["flask_githubkit.state"] = "expected"

    response = http_client.get("/callback?state=expected&error=access_denied")

    assert response.status_code == 400
    assert response.get_json() == {"message": "denied"}


def test_callback_requires_a_code(http_client):
    with http_client.session_transaction() as session:
        session["flask_githubkit.state"] = "expected"

    response = http_client.get("/callback?state=expected")

    assert response.status_code == 400
    assert response.get_json() == {
        "message": "GitHub did not return an authorization code."
    }


def test_callback_exchanges_code_and_stores_tokens(http_client, monkeypatch):
    with http_client.session_transaction() as session:
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

    response = http_client.get("/callback?state=expected&code=oauth-code")

    assert response.get_json() == {"message": "ok", "token": "access-token"}
    assert calls["credentials"] == ("client-id", "client-secret")
    assert calls["web_auth"] == ("oauth-code", "http://localhost:5000/callback")
    assert isinstance(calls["github"].auth, FakeOAuthApp)
    with http_client.session_transaction() as session:
        assert session["flask_githubkit.token"]["token"] == "access-token"
        assert session["flask_githubkit.token"]["refresh_token"] == "refresh-token"
        assert session.permanent


def test_client_is_none_when_signed_out(app, oauth):
    with app.test_request_context():
        assert oauth.client() is None


def test_client_is_cached_per_request(app, oauth):
    with app.test_request_context():
        flask.session["flask_githubkit.token"] = SAMPLE_TOKEN

        assert oauth.client() is oauth.client()


def test_invalid_stored_token_is_cleared(app, oauth):
    with app.test_request_context():
        flask.session["flask_githubkit.token"] = {"token": None, "refresh_token": None}

        assert oauth.client() is None
        assert "flask_githubkit.token" not in flask.session


def test_refreshed_token_is_written_back_to_session(app, oauth, http_client):
    @app.route("/refresh")
    def refresh():
        api = oauth.client()
        # Stand-in for GitHubKit refreshing the token in place during a call.
        api.auth.token = "new-token"
        api.auth.refresh_token = "new-refresh"
        return flask.jsonify({})

    with http_client.session_transaction() as session:
        session["flask_githubkit.token"] = {
            "token": "old-token",
            "refresh_token": "old-refresh",
            "expire_time": "2020-01-01T00:00:00+00:00",
            "refresh_token_expire_time": "2099-01-01T00:00:00+00:00",
        }

    assert http_client.get("/refresh").status_code == 200
    with http_client.session_transaction() as session:
        assert session["flask_githubkit.token"]["token"] == "new-token"
        assert session["flask_githubkit.token"]["refresh_token"] == "new-refresh"


def test_logout_removes_stored_token(app, oauth):
    with app.test_request_context():
        flask.session["flask_githubkit.token"] = SAMPLE_TOKEN

        oauth.logout()

        assert "flask_githubkit.token" not in flask.session


def test_expired_refresh_token_clears_session_and_redirects_to_login(app, http_client):
    @app.route("/expired")
    def expired():
        raise AuthExpiredError("Refresh token expired.")

    with http_client.session_transaction() as session:
        session["flask_githubkit.token"] = SAMPLE_TOKEN

    response = http_client.get("/expired")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with http_client.session_transaction() as session:
        assert "flask_githubkit.token" not in session
