"""Smoke tests: every example app must load and start the OAuth flow."""

import importlib.util
import pathlib
import urllib.parse

import pytest

EXAMPLES = pathlib.Path(__file__).parent.parent / "examples"

# The examples are not part of the wheel, so skip when testing one.
pytestmark = pytest.mark.skipif(
    not EXAMPLES.is_dir(), reason="examples/ is not available"
)

CASES = [
    ("single_file", "/login", "read:user"),
    ("factory", "/login", "read:user user:email"),
    ("blueprint", "/auth/login", "read:user"),
    ("routes", "/login", "read:user"),
]


def load_app(name):
    spec = importlib.util.spec_from_file_location(
        f"example_{name}", EXAMPLES / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.app if hasattr(module, "app") else module.create_app()


@pytest.fixture(autouse=True)
def example_env(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret")
    monkeypatch.setenv("GITHUB_CLIENT_ID", "client-id")
    monkeypatch.setenv("GITHUB_CLIENT_SECRET", "client-secret")


@pytest.mark.parametrize(("name", "path", "scope"), CASES)
def test_example_login_redirects_to_github(name, path, scope):
    client = load_app(name).test_client()

    response = client.get(path)

    location = urllib.parse.urlparse(response.headers["Location"])
    query = urllib.parse.parse_qs(location.query)
    assert response.status_code == 302
    assert location.netloc == "github.com"
    assert query["scope"] == [scope]


def test_blueprint_example_sends_expired_users_to_auth_login():
    import githubkit.exception

    app = load_app("blueprint")

    @app.route("/expired")
    def expired():
        raise githubkit.exception.AuthExpiredError("expired")

    response = app.test_client().get("/expired")

    assert response.headers["Location"].endswith("/auth/login")


def test_routes_example_redirects_signed_out_users_to_login():
    response = load_app("routes").test_client().get("/profile")

    assert response.headers["Location"].endswith("/login")
