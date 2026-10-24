from urllib.parse import parse_qs, urlparse


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
        assert session["github_oauth_state"] == query["state"][0]


def test_login_reports_missing_configuration(app, client):
    app.config["GITHUB_CLIENT_ID"] = None

    response = client.get("/login")

    assert response.status_code == 500
    assert response.get_json() == {"message": "GitHub OAuth is not configured."}

