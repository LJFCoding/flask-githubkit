# Examples

The complete, runnable apps live in the repository's
[`examples/` directory](https://github.com/LJFCoding/flask-githubkit/tree/main/examples).
The test suite smoke-tests these examples so documentation snippets do
not have to be maintained separately.

## Single-file application

Use this pattern for a small app with a module-level Flask application.
`GitHub(app)` initializes the extension immediately:

```{literalinclude} ../examples/single_file.py
:language: python
```

Run it from the repository root after setting `SECRET_KEY`,
`GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`:

```console
flask --app examples/single_file run
```

## Application factory

An application factory creates the Flask app inside a function. This
pattern is useful for tests, multiple app configurations, and larger
projects. Create the extension once, then call `init_app(app)` inside
the factory:

```{literalinclude} ../examples/factory.py
:language: python
```

## Blueprint

Blueprints give routes an endpoint prefix. In the following example,
the login endpoint is `auth.login`. The extension discovers this from
`@github.login`, so no `GITHUB_LOGIN_VIEW` setting is needed:

```{literalinclude} ../examples/blueprint.py
:language: python
```

The callback URL registered with GitHub must include the Blueprint
prefix, for example `http://localhost:5000/auth/callback`.

## Call the API from a route

`github.client()` returns a GitHubKit client for the signed-in user, or
`None` when no token is available. Use the client's typed REST methods:

```{literalinclude} ../examples/routes.py
:language: python
```

Prefer API calls over reading the access token directly. If server-side
integration code needs the token, it is available as
`client.auth.token`. It is a bearer credential: do not return it to the
browser, include it in a URL, or write it to logs. An API request may
refresh the token, so read the value after using the client if you need
the refreshed credential.
