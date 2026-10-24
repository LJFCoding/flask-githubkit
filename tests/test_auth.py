import json
import urllib.parse

import flask
import githubkit
import githubkit.auth
import githubkit.exception
import httpx
import pytest

import flask_githubkit

SAMPLE_TOKEN = {
    "token": "token",
    "refresh_token": None,
    "expire_time": None,
    "refresh_token_expire_time": None,
}


def test_login_redirects_to_github_with_state_scope_and_callback(http_client):
    response = http_client.get("/login")

    assert response.status_code == 302
    redirect = urllib.parse.urlparse(response.headers["Location"])
    query = urllib.parse.parse_qs(redirect.query)
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
    assert response.get_json() == {
        "message": "GitHub OAuth is not configured."
    }


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

    monkeypatch.setattr(githubkit.auth, "OAuthAppAuthStrategy", FakeOAuthApp)
    monkeypatch.setattr(githubkit, "GitHub", FakeGitHub)

    response = http_client.get("/callback?state=expected&code=oauth-code")

    assert response.get_json() == {"message": "ok", "token": "access-token"}
    assert calls["credentials"] == ("client-id", "client-secret")
    assert calls["web_auth"] == (
        "oauth-code",
        "http://localhost:5000/callback",
    )
    assert isinstance(calls["github"].auth, FakeOAuthApp)
    with http_client.session_transaction() as session:
        assert session["flask_githubkit.token"]["token"] == "access-token"
        assert (
            session["flask_githubkit.token"]["refresh_token"]
            == "refresh-token"
        )
        assert session.permanent


def test_client_is_none_when_signed_out(app, github):
    with app.test_request_context():
        assert github.client() is None


def test_client_is_cached_per_request(app, github):
    with app.test_request_context():
        flask.session["flask_githubkit.token"] = SAMPLE_TOKEN

        assert github.client() is github.client()


def test_invalid_stored_token_is_cleared(app, github):
    with app.test_request_context():
        flask.session["flask_githubkit.token"] = {
            "token": None,
            "refresh_token": None,
        }

        assert github.client() is None
        assert "flask_githubkit.token" not in flask.session


def test_refreshed_token_is_written_back_to_session(app, github, http_client):
    @app.route("/refresh")
    def refresh():
        api = github.client()
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
        assert (
            session["flask_githubkit.token"]["refresh_token"] == "new-refresh"
        )


def test_logout_removes_stored_token(app, github):
    with app.test_request_context():
        flask.session["flask_githubkit.token"] = SAMPLE_TOKEN

        github.logout()

        assert "flask_githubkit.token" not in flask.session


def test_expired_refresh_token_clears_session_and_redirects_to_login(
    app, http_client
):
    @app.route("/expired")
    def expired():
        raise githubkit.exception.AuthExpiredError("Refresh token expired.")

    with http_client.session_transaction() as session:
        session["flask_githubkit.token"] = SAMPLE_TOKEN

    response = http_client.get("/expired")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with http_client.session_transaction() as session:
        assert "flask_githubkit.token" not in session


def test_constructor_with_an_app_registers_the_expired_handler():
    app = flask.Flask(__name__)
    app.config["SECRET_KEY"] = "test-secret"
    flask_githubkit.GitHub(app)

    @app.route("/login")
    def login():
        return "login"

    @app.route("/expired")
    def expired():
        raise githubkit.exception.AuthExpiredError("Refresh token expired.")

    response = app.test_client().get("/expired")

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")


def test_init_app_registers_the_handler_for_each_app(github):
    for _ in range(2):
        app = flask.Flask(__name__)
        app.config["SECRET_KEY"] = "test-secret"
        github.init_app(app)

        @app.route("/login")
        def login():
            return "login"

        @app.route("/expired")
        def expired():
            raise githubkit.exception.AuthExpiredError("expired")

        assert app.test_client().get("/expired").status_code == 302


def make_expiring_app(options=None, **config):
    app = flask.Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY="test-secret", **config)
    flask_githubkit.GitHub(app, **(options or {}))

    @app.route("/expired")
    def expired():
        raise githubkit.exception.AuthExpiredError("expired")

    return app


def test_expired_handler_uses_the_configured_login_view():
    app = make_expiring_app(GITHUB_LOGIN_VIEW="signin")

    @app.route("/sign-in")
    def signin():
        return "sign in"

    response = app.test_client().get("/expired")

    assert response.headers["Location"].endswith("/sign-in")


def test_expired_handler_accepts_a_blueprint_endpoint():
    app = make_expiring_app(GITHUB_LOGIN_VIEW="auth.login")
    blueprint = flask.Blueprint("auth", __name__, url_prefix="/auth")

    @blueprint.route("/login")
    def login():
        return "login"

    app.register_blueprint(blueprint)

    response = app.test_client().get("/expired")

    assert response.headers["Location"].endswith("/auth/login")


def test_expired_handler_defaults_to_the_login_endpoint():
    app = make_expiring_app()

    @app.route("/login")
    def login():
        return "login"

    response = app.test_client().get("/expired")

    assert response.headers["Location"].endswith("/login")


def test_expired_handler_explains_an_unknown_login_view():
    app = make_expiring_app(GITHUB_LOGIN_VIEW="/auth/login")

    with pytest.raises(RuntimeError, match="GITHUB_LOGIN_VIEW '/auth/login'"):
        app.test_client().get("/expired")


def test_unknown_default_login_view_is_explained():
    app = make_expiring_app()

    with pytest.raises(RuntimeError, match="not a Flask endpoint"):
        app.test_client().get("/expired")


TOKEN_RESPONSE = {
    "access_token": "gho_new",
    "refresh_token": "ghr_new",
    "expires_in": 28800,
    "refresh_token_expires_in": 15811200,
    "token_type": "bearer",
}


def use_github_transport(monkeypatch, handler):
    """Run GitHubKit's real code exchange against a mock GitHub."""
    real_github = githubkit.GitHub
    transport = httpx.MockTransport(handler)
    monkeypatch.setattr(
        githubkit,
        "GitHub",
        lambda **kwargs: real_github(transport=transport, **kwargs),
    )


def start_callback(http_client, path="/callback?state=expected&code=abc"):
    with http_client.session_transaction() as session:
        session["flask_githubkit.state"] = "expected"
    return http_client.get(path)


def test_real_exchange_stores_the_tokens(http_client, monkeypatch):
    requests = []

    def handler(request):
        requests.append(json.loads(request.content))
        return httpx.Response(200, json=TOKEN_RESPONSE)

    use_github_transport(monkeypatch, handler)

    response = start_callback(http_client)

    assert response.get_json() == {"message": "ok", "token": "gho_new"}
    assert requests == [
        {
            "client_id": "client-id",
            "client_secret": "client-secret",
            "code": "abc",
            "redirect_uri": "http://localhost:5000/callback",
        }
    ]
    with http_client.session_transaction() as session:
        stored = session["flask_githubkit.token"]
        assert stored["refresh_token"] == "ghr_new"
        assert stored["expire_time"] is not None
        assert stored["refresh_token_expire_time"] is not None


def test_rejected_code_redirects_to_login(http_client, monkeypatch):
    use_github_transport(
        monkeypatch,
        lambda request: httpx.Response(
            200, json={"error": "bad_verification_code"}
        ),
    )

    response = start_callback(http_client)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/login")
    with http_client.session_transaction() as session:
        assert "flask_githubkit.token" not in session


def raise_timeout(request):
    raise httpx.ReadTimeout("slow", request=request)


def raise_connect_error(request):
    raise httpx.ConnectError("refused", request=request)


@pytest.mark.parametrize(
    "handler",
    [
        lambda request: httpx.Response(500, json={"message": "boom"}),
        lambda request: httpx.Response(503, text="unavailable"),
        raise_timeout,
        raise_connect_error,
    ],
    ids=["http-500", "http-503", "timeout", "connection-refused"],
)
def test_github_outage_returns_a_bad_gateway(
    http_client, monkeypatch, handler
):
    use_github_transport(monkeypatch, handler)

    response = start_callback(http_client)

    assert response.status_code == 502
    assert response.get_json() == {"message": "Could not reach GitHub."}
    with http_client.session_transaction() as session:
        assert "flask_githubkit.token" not in session


def test_github_outage_does_not_call_the_view(app, github, monkeypatch):
    calls = []

    @app.route("/other")
    @github.callback
    def other(access_token):
        calls.append(access_token)
        return "ok"

    use_github_transport(monkeypatch, raise_connect_error)
    client = app.test_client()

    start_callback(client, "/other?state=expected&code=abc")

    assert calls == []


def test_github_outage_still_consumes_the_state(http_client, monkeypatch):
    use_github_transport(monkeypatch, raise_connect_error)
    start_callback(http_client)

    with http_client.session_transaction() as session:
        assert "flask_githubkit.state" not in session


def test_login_stores_the_state_it_sends(http_client):
    response = http_client.get("/login")

    sent = urllib.parse.parse_qs(
        urllib.parse.urlparse(response.headers["Location"]).query
    )["state"][0]
    with http_client.session_transaction() as session:
        assert session["flask_githubkit.state"] == sent


def test_login_uses_a_new_state_each_time(http_client):
    states = []
    for _ in range(2):
        location = http_client.get("/login").headers["Location"]
        query = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
        states.append(query["state"][0])

    assert states[0] != states[1]


def test_login_uses_the_default_scope(app, http_client):
    del app.config["GITHUB_SCOPE"]

    location = http_client.get("/login").headers["Location"]

    query = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
    assert query["scope"] == ["read:user"]


def test_callback_reports_missing_configuration(app, http_client):
    del app.config["GITHUB_CLIENT_ID"]
    with http_client.session_transaction() as session:
        session["flask_githubkit.state"] = "expected"

    response = http_client.get("/callback?state=expected&code=abc")

    assert response.status_code == 500
    assert response.get_json() == {
        "message": "GitHub OAuth is not configured."
    }


def test_callback_rejects_a_replayed_state(http_client):
    with http_client.session_transaction() as session:
        session["flask_githubkit.state"] = "expected"

    first = http_client.get("/callback?state=expected&error=access_denied")
    second = http_client.get("/callback?state=expected&error=access_denied")

    assert first.status_code == 400
    assert first.get_json() == {"message": "denied"}
    assert second.status_code == 400
    assert second.get_json() == {"message": "Invalid OAuth state."}


def test_callback_checks_state_before_looking_for_a_code(http_client):
    response = http_client.get("/callback?code=abc")

    assert response.get_json() == {"message": "Invalid OAuth state."}


def test_callback_does_not_store_tokens_when_denied(http_client):
    with http_client.session_transaction() as session:
        session["flask_githubkit.state"] = "expected"

    http_client.get("/callback?state=expected&error=access_denied")

    with http_client.session_transaction() as session:
        assert "flask_githubkit.token" not in session


def test_callback_passes_url_arguments_to_the_view(app, github, http_client):
    @app.route("/callback/<name>")
    @github.callback
    def named(access_token, name):
        return flask.jsonify({"name": name, "token": access_token})

    with http_client.session_transaction() as session:
        session["flask_githubkit.state"] = "expected"

    response = http_client.get("/callback/bob?state=expected&error=x")

    assert response.get_json() == {"name": "bob", "token": None}


def test_callback_keeps_the_view_name(github):
    @github.callback
    def my_view(access_token):
        """My docs."""

    assert my_view.__name__ == "my_view"
    assert my_view.__doc__ == "My docs."


def test_client_is_none_when_configuration_is_missing(app, github):
    del app.config["GITHUB_CLIENT_SECRET"]

    with app.test_request_context():
        flask.session["flask_githubkit.token"] = SAMPLE_TOKEN

        assert github.client() is None


def test_client_uses_the_stored_token(app, github):
    with app.test_request_context():
        flask.session["flask_githubkit.token"] = SAMPLE_TOKEN

        client = github.client()

        assert isinstance(client, githubkit.GitHub)
        assert client.auth.token == "token"


def test_client_is_new_for_each_request(app, github, http_client):
    seen = []

    @app.route("/who")
    def who():
        seen.append(github.client())
        return "ok"

    with http_client.session_transaction() as session:
        session["flask_githubkit.token"] = SAMPLE_TOKEN

    http_client.get("/who")
    http_client.get("/who")

    assert seen[0] is not seen[1]


def test_logout_during_a_request_is_not_undone_by_the_write_back(
    app, github, http_client
):
    @app.route("/bye")
    def bye():
        github.client()
        github.logout()
        return "bye"

    with http_client.session_transaction() as session:
        session["flask_githubkit.token"] = SAMPLE_TOKEN

    http_client.get("/bye")

    with http_client.session_transaction() as session:
        assert "flask_githubkit.token" not in session


def test_unchanged_token_is_saved_again_after_a_request(
    app, github, http_client
):
    @app.route("/touch")
    def touch():
        github.client()
        return "ok"

    with http_client.session_transaction() as session:
        session["flask_githubkit.token"] = {
            "token": "token",
            "refresh_token": None,
            "expire_time": None,
            "refresh_token_expire_time": None,
        }

    http_client.get("/touch")

    with http_client.session_transaction() as session:
        assert session["flask_githubkit.token"]["token"] == "token"
        assert session.permanent


def test_logout_is_safe_when_signed_out(app, github):
    with app.test_request_context():
        github.logout()

        assert "flask_githubkit.token" not in flask.session


def test_logout_keeps_other_session_data(app, github):
    with app.test_request_context():
        flask.session["mine"] = "kept"
        flask.session["flask_githubkit.token"] = SAMPLE_TOKEN

        github.logout()

        assert flask.session["mine"] == "kept"


def scope_of(client):
    location = client.get("/login").headers["Location"]
    query = urllib.parse.parse_qs(urllib.parse.urlparse(location).query)
    return query["scope"]


def make_login_app(app_config=None, **options):
    app = flask.Flask(__name__)
    app.config.update(
        TESTING=True,
        SECRET_KEY="test-secret",
        GITHUB_CLIENT_ID="client-id",
        GITHUB_CLIENT_SECRET="client-secret",
        GITHUB_REDIRECT_URI="http://localhost:5000/callback",
        **(app_config or {}),
    )
    github = flask_githubkit.GitHub(app, **options)
    app.add_url_rule("/login", "login", github.login)
    return app


def test_constructor_scope_overrides_the_config():
    app = make_login_app({"GITHUB_SCOPE": "read:user"}, scope="repo")

    assert scope_of(app.test_client()) == ["repo"]


def test_scope_comes_from_the_config_without_a_constructor_value():
    app = make_login_app({"GITHUB_SCOPE": "repo gist"})

    assert scope_of(app.test_client()) == ["repo gist"]


def test_scope_defaults_when_neither_is_given():
    app = make_login_app()

    assert scope_of(app.test_client()) == ["read:user"]


def test_scope_can_be_set_after_init_app_is_called_later():
    app = flask.Flask(__name__)
    app.config.update(
        SECRET_KEY="test-secret",
        GITHUB_CLIENT_ID="client-id",
        GITHUB_CLIENT_SECRET="client-secret",
        GITHUB_REDIRECT_URI="http://localhost:5000/callback",
    )
    github = flask_githubkit.GitHub(scope="gist")
    github.init_app(app)
    app.add_url_rule("/login", "login", github.login)

    assert scope_of(app.test_client()) == ["gist"]


def test_constructor_login_view_overrides_the_config():
    app = make_expiring_app(
        {"login_view": "signin"}, GITHUB_LOGIN_VIEW="other"
    )

    @app.route("/sign-in")
    def signin():
        return "sign in"

    response = app.test_client().get("/expired")

    assert response.headers["Location"].endswith("/sign-in")


def test_constructor_login_view_accepts_a_blueprint_endpoint():
    app = make_expiring_app({"login_view": "auth.login"})
    blueprint = flask.Blueprint("auth", __name__, url_prefix="/auth")
    blueprint.add_url_rule("/login", "login", lambda: "login")
    app.register_blueprint(blueprint)

    response = app.test_client().get("/expired")

    assert response.headers["Location"].endswith("/auth/login")
