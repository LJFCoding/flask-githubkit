"""Flask extension for GitHub OAuth login, built on GitHubKit."""

import flask_githubkit.auth
import flask_githubkit.config
import flask_githubkit.store

GitHub = flask_githubkit.auth.GitHub
Config = flask_githubkit.config.Config
Token = flask_githubkit.store.Token

__all__ = ["Config", "GitHub", "Token"]
