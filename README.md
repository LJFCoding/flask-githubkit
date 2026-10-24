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
from flask_githubkit import GitHubOAuth

app = flask.Flask(__name__)
app.config.update(
    SECRET_KEY="load-this-from-a-secret-manager",
    GITHUB_CLIENT_ID="your-client-id",
    GITHUB_CLIENT_SECRET="load-this-from-a-secret-manager",
    GITHUB_REDIRECT_URI="https://example.com/callback",
)

github = GitHubOAuth(app, scope="read:user", login_endpoint="login")


@app.route("/login")
def login():
    return github.authorize()


@app.route("/callback")
@github.authorized_handler
def callback(access_token):
    if access_token is None:
        return flask.jsonify({"message": "GitHub authorization was denied"}), 401
    return flask.jsonify({"message": "Signed in"})


@app.route("/me")
def me():
    api = github.client()
    if api is None:
        return flask.redirect(flask.url_for("login"))
    user = api.rest.users.get_authenticated().parsed_data
    return flask.jsonify({"login": user.login})
```

`authorized_handler` validates the OAuth `state`, exchanges the authorization
code, stores the token data, and calls the decorated view with the access token.
If the user denies access, the view receives `None`. Protect callback handling
with the decorator as shown; it is responsible for validating `state`.

With an application factory, create the extension once and initialize it for
each app:

```python
github = GitHubOAuth(scope="read:user")


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
