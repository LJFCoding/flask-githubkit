# flask-githubkit

A Flask extension for GitHub OAuth login, built on
[GitHubKit](https://github.com/yanyongyu/githubkit). It handles expiring-token
refresh and stores tokens in `flask.session`.

## Installation

Install the release directly from GitHub:

```console
pip install "flask-githubkit @ git+https://github.com/LJFCoding/flask-githubkit.git@v0.1.0"
```

It is not published on PyPI yet, so `pip install flask-githubkit` will not
find it. It requires Python 3.10+ and installs Flask, GitHubKit and httpx.

For local development, install the test dependencies with
`pip install -e ".[test]"`.

## How it works

1. `github.login()` redirects the user to GitHub with a random `state` value
   that is kept in `flask.session`.
2. GitHub redirects back to your callback URL with a `code` and the `state`.
3. `@github.callback` checks the `state` (blocking login CSRF), exchanges the
   `code` for tokens through GitHubKit, saves them in `flask.session`, and
   calls your view with the access token.
4. In any later request, `github.client()` returns a GitHubKit client for that
   user. GitHubKit refreshes an expired access token itself, and the new
   token values are saved back to the session when the request finishes.

The names follow [Flask-GitHub](https://github.com/cenkalti/github-flask), but
the API is smaller and the HTTP calls are made by
[GitHubKit](https://github.com/yanyongyu/githubkit), so you get its typed
`rest` methods instead of raw `get`/`post` helpers. Only synchronous Flask
apps are supported.

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
    GITHUB_SCOPE="read:user",
)

github = flask_githubkit.GitHub(app)


@app.route("/login")
@github.login
def login():
    """Replaced by a redirect to GitHub."""


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
github = flask_githubkit.GitHub()


def create_app():
    app = flask.Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY="load-this-from-a-secret-manager",
        GITHUB_CLIENT_ID="your-client-id",
        GITHUB_CLIENT_SECRET="load-this-from-a-secret-manager",
        GITHUB_REDIRECT_URI="https://example.com/callback",
        GITHUB_SCOPE="read:user",
    )
    github.init_app(app)
    return app
```

## Examples

Each file in [examples/](examples) is a complete app. They are checked by the
test suite, which confirms the login route redirects to GitHub.

| File | Shows |
| --- | --- |
| [single_file.py](examples/single_file.py) | A module-level app with `GitHub(app)` |
| [factory.py](examples/factory.py) | An app factory with `init_app` and the optional config keys |
| [blueprint.py](examples/blueprint.py) | Login routes in a blueprint; the `auth.login` endpoint is found from `@github.login` |
| [routes.py](examples/routes.py) | A `login_required` decorator and a route that calls the GitHub API |

Set `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` and `SECRET_KEY` in your
environment, then run one with, for example,
`flask --app examples/single_file run`.

Calling the API goes through GitHubKit, so see its
[documentation](https://yanyongyu.github.io/githubkit/) for everything
`client().rest` offers.

## Coming from Flask-GitHub

| Flask-GitHub | flask-githubkit |
| --- | --- |
| `GitHub(app)` | `GitHub(app)` or `init_app(app)` |
| `github.authorize()` | `@github.login`, or `github.login()` in a view |
| `@github.authorized_handler` | `@github.callback` |
| `@github.access_token_getter` | Not needed: tokens are kept in `flask.session` |
| `github.get("user")` | `github.client().rest.users.get_authenticated()` |
| `authorize(scope=..., redirect_uri=...)` | Not supported: use `scope=` in `GitHub(...)` or `GITHUB_SCOPE`, and `GITHUB_REDIRECT_URI` |

## Configuration and API

| Flask config key | Required | Purpose |
| --- | --- | --- |
| `GITHUB_CLIENT_ID` | Yes | GitHub OAuth App client ID |
| `GITHUB_CLIENT_SECRET` | Yes | GitHub OAuth App client secret |
| `GITHUB_REDIRECT_URI` | Yes | Callback URL registered with the OAuth App |
| `SECRET_KEY` | Yes | Flask session signing key |
| `GITHUB_SCOPE` | No | Space-separated OAuth scopes to request. Default `read:user`. |
| `GITHUB_LOGIN_VIEW` | No | Endpoint name users are sent to when their refresh token has expired. Usually not needed: see below. It is an endpoint name such as `auth.login`, not a URL. |

`flask_githubkit.GitHub(app=None, *, scope=None, login_view=None)` accepts an
optional Flask app. Use `init_app(app)` to initialize it later.

`scope` and `login_view` are optional. Each one is taken from the constructor
if you pass it, otherwise from `GITHUB_SCOPE` or `GITHUB_LOGIN_VIEW` in the
Flask config. If neither is set, the scope is `read:user`. The login view is
the view you decorated with `@github.login`, with its blueprint prefix
(`auth.login`), or an endpoint named `login` if there is no decorated view.
The client ID, client secret, redirect URI and `SECRET_KEY` always come from
the Flask config.

```python
github = flask_githubkit.GitHub(
    scope="read:user repo", login_view="auth.login"
)
```

- `@github.login` turns a view into a redirect to GitHub that starts the
  OAuth flow. You can also call `github.login()` inside a view and return
  the result, which is useful if you want to run code first. The decorated
  function's body never runs.
- `@callback` wraps the callback view.
- `client()` returns the request-cached GitHubKit `GitHub` client, or `None`
  when there is no valid stored token.
- `logout()` removes the stored GitHub token from the session.

The extension registers an `AuthExpiredError` handler that clears the stored
token and redirects to the login view. GitHubKit also raises
`AuthExpiredError` when GitHub rejects the authorization code, so a stale or
reused code sends the user back to login. If GitHub cannot be reached while
exchanging the code (a timeout, a connection error or a 5xx response), the
callback returns a `502` JSON error, `Could not reach GitHub.`, and does not
call your view. If the login view is not a real
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
this package does not provide a distributed lock. Errors raised while your own
code uses `client()` (for example a network failure during an API call) are not
caught by the extension.

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

CI also requires 100% line and branch coverage:

```console
coverage run -m pytest
coverage report
```
