"""Flask extension for GitHub OAuth login, built on GitHubKit."""

import flask_githubkit.auth
import flask_githubkit.config
import flask_githubkit.token

GitHubOAuth = flask_githubkit.auth.GitHubOAuth
Config = flask_githubkit.config.Config
Store = flask_githubkit.token.Store

__all__ = ["Config", "GitHubOAuth", "Store"]
