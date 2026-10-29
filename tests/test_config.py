import flask
import pytest

import flask_githubkit

KEYS = (
    "GITHUB_CLIENT_ID",
    "GITHUB_CLIENT_SECRET",
    "SECRET_KEY",
)


def test_config_redirect_uri_is_optional(app):
    del app.config["GITHUB_REDIRECT_URI"]

    with app.app_context():
        config = flask_githubkit.Config.from_current_app()

    assert config.redirect_uri is None


def test_config_reads_the_app_settings(app):
    with app.app_context():
        config = flask_githubkit.Config.from_current_app()

    assert config == flask_githubkit.Config(
        client_id="client-id",
        client_secret="client-secret",
        redirect_uri="http://localhost:5000/callback",
        scope="read:user repo",
    )


def test_config_scope_defaults_to_read_user(app):
    del app.config["GITHUB_SCOPE"]

    with app.app_context():
        config = flask_githubkit.Config.from_current_app()

    assert config.scope == "read:user"


@pytest.mark.parametrize("scope", ["", 123, ["read:user"]])
def test_config_is_none_when_the_scope_is_invalid(app, scope):
    app.config["GITHUB_SCOPE"] = scope

    with app.app_context():
        assert flask_githubkit.Config.from_current_app() is None


@pytest.mark.parametrize("key", KEYS)
def test_config_is_none_when_a_key_is_missing(app, key):
    del app.config[key]

    with app.app_context():
        assert flask_githubkit.Config.from_current_app() is None


@pytest.mark.parametrize("key", KEYS)
def test_config_is_none_when_a_key_is_empty(app, key):
    app.config[key] = ""

    with app.app_context():
        assert flask_githubkit.Config.from_current_app() is None


@pytest.mark.parametrize("key", KEYS)
def test_config_is_none_when_a_key_is_not_a_string(app, key):
    app.config[key] = 123

    with app.app_context():
        assert flask_githubkit.Config.from_current_app() is None


def test_config_is_frozen(app):
    with app.app_context():
        config = flask_githubkit.Config.from_current_app()

    with pytest.raises(AttributeError):
        config.client_id = "other"


def test_config_needs_no_request(app):
    with app.app_context():
        assert not flask.has_request_context()
        assert flask_githubkit.Config.from_current_app() is not None
