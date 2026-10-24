# flask-githubkit

A Flask extension for GitHub OAuth login, built on
[GitHubKit](https://github.com/yanyongyu/githubkit). It handles expiring-token
refresh and stores tokens in `flask.session`.

## Installation

Install the release directly from GitHub:

```console
pip install "flask-githubkit @ git+https://github.com/LJFCoding/flask-githubkit.git@v0.1.0"
```

For local development, install the test dependencies with
`pip install -e ".[test]"`.

## Quick start

Register a GitHub OAuth App and set its callback URL to the value of
`GITHUB_REDIRECT_URI`. Enable **Expire user authorization tokens** in the
OAuth App settings if you want GitHub to issue refresh tokens.

```python
import flask
import flask_githubkit

app = flask.Flask(__name__)
app.config.update(
    SECRET_KEY="load-this-from-a-secret-manager",
    GITHUB_CLIENT_ID="your-client-id",
    GITHUB_CLIENT_SECRET="load-this-from-a-secret-manager",
    GITHUB_REDIRECT_URI="https://example.com/callback",
)

github = flask_githubkit.GitHub(app, scope="read:user")


@app.route("/login")
def login():
    return github.login()


@app.route("/callback")
@github.callback
def callback(access_token):
    if access_token is None:
        return flask.jsonify(
            {"message": "GitHub authorization was denied"}
        ), 401
    return flask.jsonify({"message": "Signed in"})


@app.route("/me")
def me():
    api = github.client()
    if api is None:
        return flask.redirect(flask.url_for("login"))
    user = api.rest.users.get_authenticated().parsed_data
    return flask.jsonify({"login": user.login})
```

`callback` validates the OAuth `state`, exchanges the authorization
code, stores the token data, and calls the decorated view with the access token.
If the user denies access, the view receives `None`. Protect callback handling
with the decorator as shown; it is responsible for validating `state`.

With an application factory, create the extension once and initialize it for
each app:

```python
github = flask_githubkit.GitHub(scope="read:user")


def create_app():
    app = flask.Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY="load-this-from-a-secret-manager",
        GITHUB_CLIENT_ID="your-client-id",
        GITHUB_CLIENT_SECRET="load-this-from-a-secret-manager",
        GITHUB_REDIRECT_URI="https://example.com/callback",
    )
    github.init_app(app)
    return app
```

## Configuration and API

| Flask config key | Required | Purpose |
| --- | --- | --- |
| `GITHUB_CLIENT_ID` | Yes | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | Yes | GitHub OAuth App client secret |
| `GITHUB_REDIRECT_URI` | Yes | Callback URL registered with the OAuth App |
| `SECRET_KEY` | Yes | Flask session signing key |
| `GITHUB_LOGIN_VIEW` | No | Endpoint name users are sent to when their refresh token has expired. Default `login`; use `auth.login` for a `login` view in a blueprint named `auth`. It is an endpoint name, not a URL. |

`flask_githubkit.GitHub(app=None, *, scope="read:user")` accepts an optional
Flask app. Use `init_app(app)` to initialize it later.

- `login()` starts the OAuth flow and redirects to GitHub.
- `@callback` wraps the callback view.
- `client()` returns the request-cached GitHubKit `GitHub` client, or `None`
  when there is no valid stored token.
- `logout()` removes the stored GitHub token from the session.

The extension registers an `AuthExpiredError` handler that clears the stored
token and redirects to `GITHUB_LOGIN_VIEW`. GitHubKit also raises
`AuthExpiredError` when GitHub rejects the authorization code, so a stale or
reused code sends the user back to login. If `GITHUB_LOGIN_VIEW` is not a real
endpoint, the handler raises a `RuntimeError` that says so.

`flask_githubkit.Config.from_current_app()` reads the configuration keys above.
`flask_githubkit.Token` serializes token expiry datetimes as ISO-formatted
strings in `flask.session`.

## Sessions, token refresh, and limitations

The default Flask session is a signed, client-side cookie; it is **not
encrypted**, so users can read its contents. This package stores OAuth token
data there, so use a server-side session backend such as Flask-Session with
Redis in production. The extension only uses `flask.session` and marks the
session permanent when it saves tokens. Configure your backend and
`PERMANENT_SESSION_LIFETIME` (for example, 30 days) in your application; sliding
expiry and TTL behavior depend on that backend and are not provided by this
package.

GitHubKit refreshes expired access tokens when the client is used. The extension
writes updated token values back to the session after the request. GitHub
refresh tokens are single-use, so concurrent requests can race while refreshing;
this package does not provide a distributed lock.

This package supports synchronous Flask apps and GitHub OAuth Apps. It does not
support GitHub Apps or configure GitHub Enterprise endpoints. Real GitHub code
exchange and refresh, Redis operation, and Flask-Session TTL behavior require
integration testing against those services and are not verified by the
automated tests in this repository.

## Tests

```console
pip install -e ".[test]"
pytest
```
