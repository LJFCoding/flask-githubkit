# Quick start

This tutorial builds a small Flask app with GitHub login, a callback, a
profile route that calls GitHub, and logout.

## Before you start

1. [Install the package](installation.md).
2. [Create a GitHub OAuth App](installation.md#register-a-github-oauth-app).
3. Set its callback URL to `http://localhost:5000/callback`.

For local development, provide the OAuth credentials and a Flask secret in
your shell:

```console
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_hex(32))')"
export GITHUB_CLIENT_ID="your-oauth-app-client-id"
export GITHUB_CLIENT_SECRET="your-oauth-app-client-secret"
```

The generated `SECRET_KEY` is for local development. Keep it stable while
you use the app; changing it invalidates Flask's signed session cookies.
For deployed applications, supply secrets through your platform's secret
manager or environment configuration.

## Create `app.py`

```python
import os

import flask
import flask_githubkit

app = flask.Flask(__name__)
app.config.from_mapping(
    SECRET_KEY=os.environ["SECRET_KEY"],
    GITHUB_CLIENT_ID=os.environ["GITHUB_CLIENT_ID"],
    GITHUB_CLIENT_SECRET=os.environ["GITHUB_CLIENT_SECRET"],
    GITHUB_SCOPE="read:user",
)

github = flask_githubkit.GitHub(app)


@app.route("/")
def index():
    return (
        '<a href="/login">Sign in with GitHub</a> '
        '<a href="/profile">View profile</a> '
        '<a href="/logout">Sign out</a>'
    )


@app.route("/login")
@github.login
def login():
    """The decorator redirects to GitHub; this body is not called."""


@app.route("/callback")
@github.callback
def callback(access_token):
    if access_token is None:
        return "GitHub authorization was denied.", 401
    return flask.redirect(flask.url_for("profile"))


@app.route("/profile")
def profile():
    client = github.client()
    if client is None:
        return flask.redirect(flask.url_for("login"))

    user = client.rest.users.get_authenticated().parsed_data
    return flask.jsonify(login=user.login)


@app.route("/logout")
def logout():
    github.logout()
    return flask.redirect(flask.url_for("index"))
```

## Run the app

From the directory containing `app.py`, start Flask:

```console
flask --app app run
```

Open `http://localhost:5000/` and choose **Sign in with GitHub**.
Completing the flow requires a working OAuth App and network access to
GitHub.

```{note}
On recent macOS versions, AirPlay Receiver can occupy port 5000. If Flask
cannot bind to it, disable AirPlay Receiver or run on another port, and
use the same port in the OAuth App's callback URL.
```

## What happens during login

1. `@github.login` redirects the browser to GitHub and stores a random
   `state` value in the Flask session.
2. GitHub sends the browser back to the `@github.callback` route with an
   authorization code and the `state`.
3. `@github.callback` checks and consumes the `state`. If it is valid, the
   extension exchanges the code for a token, saves the token in the session,
   and calls `callback(access_token)`.
4. The profile route calls `github.client()`. The extension loads the
   session token and returns a GitHubKit client for the request.
5. GitHubKit refreshes an expired access token when the client is used.
   flask-githubkit saves the updated token values to the session after the
   request.

The profile route does not need the `access_token` argument from the
callback. The extension persists the token in the session so later routes
can use `github.client()`. Prefer GitHubKit API methods over handling the
raw token.

## Denied and invalid callbacks

If the user denies authorization, the decorated callback view is called
with `None`, allowing your app to show a message or redirect. A callback
with missing or invalid `state` is rejected with HTTP 400 before the view
runs. The one-time state value is consumed on the first callback attempt,
so a replay is rejected.

For application factories and Blueprints, see
[complete examples](examples.md).
