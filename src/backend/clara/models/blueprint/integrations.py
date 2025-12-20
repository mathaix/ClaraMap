"""Integration specification models for Interview Blueprint."""

from pydantic import BaseModel, Field


class IntegrationSpec(BaseModel):
    """External integrations configuration."""

    output_destinations: list[dict] = Field(
        default_factory=list,
        description="Where to send outputs ({type, config})",
    )
    notifications: list[dict] = Field(
        default_factory=list,
        description="Notification configurations ({event, channel, recipients})",
    )
    webhooks: list[dict] = Field(
        default_factory=list,
        description="Webhook configurations ({url, events, auth})",
    )
