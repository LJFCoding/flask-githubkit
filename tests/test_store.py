import flask

import flask_githubkit.store


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
