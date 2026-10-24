# API reference

The package's public imports are `GitHub`, `Config` and `Token`:

```python
import flask_githubkit

github = flask_githubkit.GitHub()
```

Most applications only need `GitHub`. The extension handles callback
state validation, code exchange and token persistence. Application code
uses `github.client()` to make GitHub API calls.

## `GitHub`

The generated reference below documents the public extension methods
and their signatures.

```{eval-rst}
.. autoclass:: flask_githubkit.GitHub
   :members: init_app, login, callback, client, logout
```

### Callback behavior

`@github.callback` checks and consumes the one-time OAuth `state` value
before calling the decorated view. Invalid or replayed state returns
HTTP 400 and the view is not called. If the user denies authorization,
the view receives `None`. When the exchange succeeds, the view receives
the access token as its first argument.

If GitHub redirects back without an authorization code, the extension
returns HTTP 400. Network failures while exchanging the code return HTTP 502. If the
GitHubKit client later raises `AuthExpiredError`, the extension clears
the token and redirects to the configured or discovered login endpoint.

## `Config`

`Config.from_current_app()` reads the OAuth client ID, client secret,
redirect URI, scope and Flask `SECRET_KEY` from the active Flask app.
It returns `None` when required configuration is missing or invalid.
Most applications do not need to construct or call `Config` directly.

## `Token`

`Token` serializes and restores the GitHubKit OAuth token strategy in
`flask.session`. Application code normally uses `GitHub.callback`,
`GitHub.client()` and `GitHub.logout()` instead of calling `Token`
directly.

For GitHubKit's complete API, see its
[REST API documentation](https://yanyongyu.github.io/githubkit/).
