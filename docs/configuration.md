# Configuration

The extension reads OAuth credentials from the active Flask application's
config. Configure the app before serving requests.

## Flask configuration

| Key | Required | Default | Purpose |
| --- | --- | --- | --- |
| `SECRET_KEY` | Yes | — | Flask session signing key. Keep it secret and stable. |
| `GITHUB_CLIENT_ID` | Yes | — | Client ID from your GitHub OAuth App. |
| `GITHUB_CLIENT_SECRET` | Yes | — | Client secret from your GitHub OAuth App. |
| `GITHUB_REDIRECT_URI` | No | — | Absolute callback URL registered with the OAuth App. Defaults to the `@github.callback` route on the current host. Set it behind a proxy that hides the public host. |
| `GITHUB_SCOPE` | No | `read:user` | Space-separated OAuth scopes requested at login. |
| `GITHUB_LOGIN_VIEW` | No | Decorated login view, otherwise `login` | Flask endpoint to use when a refresh token has expired. |

The client ID, client secret, scope and `SECRET_KEY` must be non-empty
strings. If any is missing or empty, the login route returns a
JSON error with HTTP 500, the callback route returns the same error once its
`state` check passes, and `github.client()` returns `None`.

## Callback URL

You do not need to set `GITHUB_REDIRECT_URI`. When it is unset, the
extension finds the route decorated with `@github.callback` and builds its
URL from the current request's host. The endpoint is found once, on the
first request, and kept in `GITHUB_CALLBACK_VIEW`. If no route is decorated
and `GITHUB_REDIRECT_URI` is unset, the login route raises a `RuntimeError`.

The URL must match the callback URL registered with the OAuth App.

### Behind a proxy

Flask builds the host from the incoming request. Behind a reverse proxy
that terminates HTTPS or rewrites the host, Flask may see
`http://127.0.0.1:8000` instead of your public address, and GitHub rejects
the callback with a `redirect_uri` mismatch. Tell Flask to trust the
proxy's forwarded headers:

```python
from werkzeug.middleware.proxy_fix import ProxyFix

app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
```

Only do this when a proxy you control sets those headers, because clients
can forge them otherwise. Alternatively, set `GITHUB_REDIRECT_URI` to the
public callback URL, which is then used as-is.

## Initialize the extension

For a single app, pass the app to the extension:

```python
github = flask_githubkit.GitHub(app)
```

For an application factory, create the extension without an app and call
`init_app` when the app is created:

```python
github = flask_githubkit.GitHub()


def create_app():
    app = flask.Flask(__name__)
    app.config.from_mapping(...)
    github.init_app(app)
    return app
```

See [application factory and Blueprint examples](examples.md).

## Scope and login endpoint overrides

The constructor accepts optional `scope` and `login_view` keyword
arguments:

```python
github = flask_githubkit.GitHub(
    scope="read:user repo",
    login_view="auth.login",
)
```

For either option, the constructor value takes precedence over its Flask
config key. If no scope is supplied, the default is `read:user`. If no
login endpoint is supplied, the extension looks for a route decorated
with `@github.login` and uses its Flask endpoint. This works with
Blueprints (for example, `auth.login`). If no decorated route exists, it
uses the endpoint named `login`.

`login_view` is an endpoint name used by `flask.url_for`, not a URL path.
Most apps do not need to set it when they decorate their login route with
`@github.login`.

Scopes determine what user access the OAuth App requests. Request only
the access your app needs. GitHub's OAuth scope behavior is documented
in the [GitHub OAuth scopes guide](https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/scopes-for-oauth-apps).

## Session storage

Tokens are stored in `flask.session`. The extension marks the session
permanent when it saves tokens, but does not select or configure a
session backend or its expiration policy.

Flask's default session is a signed client-side cookie; it is **not
encrypted**, so users can read its contents. For production, use a
server-side session backend, such as Flask-Session with Redis, and
configure the backend and session lifetime for your application.
Sliding expiry and TTL behavior depend on that backend.

## Token refresh

Enable **Expire user authorization tokens** in the GitHub OAuth App if
you want expiring access tokens and refresh tokens. GitHubKit refreshes
an expired access token when an API request uses the client.
flask-githubkit writes the updated token values back to the session after
the request.

GitHub refresh tokens are single-use. Concurrent requests using the same
expired token can race; this extension does not provide a distributed
lock. A deployment that needs coordination across workers must implement
that policy in its own storage or infrastructure.

## Limitations

- Only synchronous Flask applications and GitHub OAuth Apps are supported.
  GitHub Apps and GitHub Enterprise endpoints are not configurable.
- Real GitHub code exchange and token refresh, Redis, and Flask-Session TTL
  behavior are not verified by the automated tests. Test them against those
  services before relying on them in production.
- Errors raised by your own API calls, such as network failures, are not
  caught by the extension.
