"""Flask extension for GitHub OAuth login, built on GitHubKit."""

import flask_githubkit.auth
import flask_githubkit.config
import flask_githubkit.token_store

GitHubOAuth = flask_githubkit.auth.GitHubOAuth
Config = flask_githubkit.config.Config
TokenStore = flask_githubkit.token_store.TokenStore

__all__ = ["Config", "GitHubOAuth", "TokenStore"]
