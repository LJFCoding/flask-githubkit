from dataclasses import dataclass


@dataclass(frozen=True)
class OAuthConfiguration:
    """OAuth App settings for the GitHub web flow."""

    client_id: str
    client_secret: str
    callback_url: str
