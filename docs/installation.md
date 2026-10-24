# Installation

## Install flask-githubkit

The package requires Python 3.10 or later. Install the latest release from
PyPI:

```console
python -m pip install flask-githubkit
```

To pin the version used by your project:

```console
python -m pip install "flask-githubkit==0.1.2"
```

You can also install a release directly from GitHub:

```console
python -m pip install \
  "flask-githubkit @ git+https://github.com/LJFCoding/flask-githubkit.git@v0.1.2"
```

The package installs Flask, GitHubKit and httpx as dependencies.

## Register a GitHub OAuth App

GitHub needs an OAuth App to identify your Flask application during login.
Create one in GitHub under **Settings → Developer settings → OAuth Apps →
New OAuth App**.

For the homepage, provide the URL of your application. For the callback URL,
enter the exact URL of the Flask route decorated with `@github.callback`.
For example:

| Flask route | Callback URL |
| --- | --- |
| `/callback` | `http://localhost:5000/callback` |
| Blueprint route `/auth/callback` | `http://localhost:5000/auth/callback` |

The callback URL must match the `GITHUB_REDIRECT_URI` value used by your
application. For production, use your application's HTTPS URL.

Copy the OAuth App's **Client ID** and **Client secret** into your local
environment or secrets manager. Never commit the client secret to Git.

### Enable expiring user tokens

If you want GitHubKit to refresh user access tokens automatically, enable
**Expire user authorization tokens** in the OAuth App settings. Without
expiring tokens, GitHub may issue a non-expiring access token, and there is
no refresh token to renew it.

Continue to the [quick start](quickstart.md) to configure Flask and add
the login routes.
