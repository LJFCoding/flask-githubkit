"""Flask extension for GitHub OAuth login, built on GitHubKit."""

import flask_githubkit.auth
import flask_githubkit.config
import flask_githubkit.token

GitHub = flask_githubkit.auth.GitHub
Config = flask_githubkit.config.Config
Store = flask_githubkit.token.Store

__all__ = ["Config", "GitHub", "Store"]
