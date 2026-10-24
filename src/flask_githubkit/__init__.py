"""Flask extension for GitHub OAuth login, built on GitHubKit."""

import flask_githubkit.auth
import flask_githubkit.configuration
import flask_githubkit.token_store

GitHubOAuth = flask_githubkit.auth.GitHubOAuth
OAuthConfiguration = flask_githubkit.configuration.OAuthConfiguration
TokenStore = flask_githubkit.token_store.TokenStore

__all__ = ["GitHubOAuth", "OAuthConfiguration", "TokenStore"]
