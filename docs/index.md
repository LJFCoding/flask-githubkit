# flask-githubkit

**GitHub OAuth for Flask, with GitHubKit's typed API client.**

`flask-githubkit` connects Flask routes to GitHub's OAuth flow and API. It
validates the OAuth callback's `state`, stores user tokens in the Flask
session, and saves refreshed token values after API calls.

```python
@app.route("/login")
@github.login
def login():
    """Redirect the user to GitHub."""


@app.route("/callback")
@github.callback
def callback(access_token):
    if access_token is None:
        return "GitHub authorization was denied.", 401
    return flask.redirect(flask.url_for("profile"))
```

## What you get

- A GitHub OAuth login flow designed for Flask.
- Callback state validation to protect against login CSRF.
- GitHubKit's typed REST API client, cached for the current request.
- Automatic refresh of expiring user tokens when the client is used, with
  refreshed tokens saved back to the Flask session.
- Support for Flask application factories and Blueprints.
- A small synchronous API: `@github.login`, `@github.callback`,
  `github.client()` and `github.logout()`.

Token refresh requires a GitHub OAuth App configured to issue expiring user
authorization tokens. GitHub refresh tokens are single-use, so simultaneous
requests can race while refreshing. Flask's default session cookie is signed
but not encrypted; see [session security](configuration.md).

## Start here

```{toctree}
:maxdepth: 2

installation
quickstart
configuration
examples
api
```

For GitHubKit's REST methods and other client features, see the
[GitHubKit documentation](https://yanyongyu.github.io/githubkit/). This
extension currently supports synchronous Flask applications.
