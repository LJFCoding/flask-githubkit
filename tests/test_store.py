import datetime

import flask
import githubkit.auth
import pytest

import flask_githubkit
import flask_githubkit.store

EXPIRE = datetime.datetime(2030, 1, 1, 12, 30)
REFRESH_EXPIRE = datetime.datetime(2031, 6, 15, 8, 0)


@pytest.fixture
def config():
    return flask_githubkit.Config("client-id", "client-secret", "http://x")


def make_strategy(**overrides):
    values = {
        "client_id": "client-id",
        "client_secret": "client-secret",
        "token": "access",
        "refresh_token": "refresh",
        "expire_time": EXPIRE,
        "refresh_token_expire_time": REFRESH_EXPIRE,
    }
    values.update(overrides)
    return githubkit.auth.OAuthTokenAuthStrategy(**values)


def test_token_save_stores_plain_strings(app):
    with app.test_request_context():
        flask_githubkit.store.Token.save(make_strategy())

        assert flask.session["flask_githubkit.token"] == {
            "token": "access",
            "refresh_token": "refresh",
            "expire_time": "2030-01-01T12:30:00",
            "refresh_token_expire_time": "2031-06-15T08:00:00",
        }


def test_token_save_makes_the_session_permanent(app):
    with app.test_request_context():
        assert not flask.session.permanent

        flask_githubkit.store.Token.save(make_strategy())

        assert flask.session.permanent


def test_token_save_keeps_missing_dates_as_none(app):
    strategy = make_strategy(
        refresh_token=None, expire_time=None, refresh_token_expire_time=None
    )

    with app.test_request_context():
        flask_githubkit.store.Token.save(strategy)
        payload = flask.session["flask_githubkit.token"]

        assert payload["refresh_token"] is None
        assert payload["expire_time"] is None
        assert payload["refresh_token_expire_time"] is None


def test_token_save_replaces_the_previous_tokens(app):
    with app.test_request_context():
        flask_githubkit.store.Token.save(make_strategy(token="old"))
        flask_githubkit.store.Token.save(make_strategy(token="new"))

        assert flask.session["flask_githubkit.token"]["token"] == "new"


def test_token_round_trip(app, config):
    with app.test_request_context():
        flask_githubkit.store.Token.save(make_strategy())
        loaded = flask_githubkit.store.Token.load(config)

    assert loaded.token == "access"
    assert loaded.refresh_token == "refresh"
    assert loaded.expire_time == EXPIRE
    assert loaded.refresh_token_expire_time == REFRESH_EXPIRE
    assert loaded.client_id == "client-id"
    assert loaded.client_secret == "client-secret"


def test_non_expiring_token_round_trip(app, config):
    strategy = make_strategy(
        refresh_token=None, expire_time=None, refresh_token_expire_time=None
    )

    with app.test_request_context():
        flask_githubkit.store.Token.save(strategy)
        loaded = flask_githubkit.store.Token.load(config)

    assert loaded.token == "access"
    assert loaded.refresh_token is None
    assert loaded.expire_time is None
    assert loaded.refresh_token_expire_time is None


def test_token_load_is_none_when_empty(app, config):
    with app.test_request_context():
        assert flask_githubkit.store.Token.load(config) is None


def test_token_load_ignores_a_value_that_is_not_a_dict(app, config):
    with app.test_request_context():
        flask.session["flask_githubkit.token"] = "not-a-dict"

        assert flask_githubkit.store.Token.load(config) is None


def test_token_load_clears_a_bad_date(app, config):
    with app.test_request_context():
        flask_githubkit.store.Token.save(make_strategy())
        flask.session["flask_githubkit.token"]["expire_time"] = "garbage"

        assert flask_githubkit.store.Token.load(config) is None
        assert not flask_githubkit.store.Token.exists()


def test_token_load_clears_a_non_string_date(app, config):
    with app.test_request_context():
        flask_githubkit.store.Token.save(make_strategy())
        flask.session["flask_githubkit.token"]["expire_time"] = 5

        assert flask_githubkit.store.Token.load(config) is None
        assert not flask_githubkit.store.Token.exists()


def test_token_load_clears_a_payload_with_no_tokens(app, config):
    with app.test_request_context():
        flask.session["flask_githubkit.token"] = {}

        assert flask_githubkit.store.Token.load(config) is None
        assert not flask_githubkit.store.Token.exists()


def test_token_exists_and_clear(app):
    with app.test_request_context():
        assert not flask_githubkit.store.Token.exists()

        flask_githubkit.store.Token.save(make_strategy())
        assert flask_githubkit.store.Token.exists()

        flask_githubkit.store.Token.clear()
        assert not flask_githubkit.store.Token.exists()


def test_token_clear_is_safe_when_empty(app):
    with app.test_request_context():
        flask_githubkit.store.Token.clear()

        assert not flask_githubkit.store.Token.exists()


def test_token_clear_keeps_other_session_data(app):
    with app.test_request_context():
        flask.session["mine"] = "kept"
        flask_githubkit.store.Token.save(make_strategy())

        flask_githubkit.store.Token.clear()

        assert flask.session["mine"] == "kept"


def test_state_is_valid_once(app):
    with app.test_request_context():
        state = flask_githubkit.store.State.new()

        assert flask_githubkit.store.State.check(state)
        assert not flask_githubkit.store.State.check(state)


def test_state_rejects_a_different_value(app):
    with app.test_request_context():
        flask_githubkit.store.State.new()

        assert not flask_githubkit.store.State.check("other")
        assert "flask_githubkit.state" not in flask.session


def test_state_is_saved_in_the_session(app):
    with app.test_request_context():
        state = flask_githubkit.store.State.new()

        assert flask.session["flask_githubkit.state"] == state


def test_state_values_are_random_and_long(app):
    with app.test_request_context():
        first = flask_githubkit.store.State.new()
        second = flask_githubkit.store.State.new()

    assert first != second
    assert len(first) >= 32


def test_state_check_fails_when_none_was_issued(app):
    with app.test_request_context():
        assert not flask_githubkit.store.State.check("anything")
        assert not flask_githubkit.store.State.check("")


def test_state_check_rejects_an_empty_value(app):
    with app.test_request_context():
        flask_githubkit.store.State.new()

        assert not flask_githubkit.store.State.check("")
