"""Extraction schema models for Interview Blueprint."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field


class FieldType(StrEnum):
    """Supported field types for entity extraction."""

    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ENUM = "enum"
    LIST = "list"
    DATE = "date"
    DATETIME = "datetime"


class FieldSpec(BaseModel):
    """Field specification within an entity."""

    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]*$")
    type: FieldType
    required: bool = False
    description: str
    enum_values: list[str] | None = Field(None, description="Allowed values for enum type")
    validation_rules: list[str] | None = Field(None, description="Additional validation rules")
    default: Any | None = None


class EntitySpec(BaseModel):
    """Entity to extract from interviews."""

    name: str = Field(
        ...,
        pattern=r"^[A-Z][a-zA-Z0-9]*$",
        description="PascalCase entity name",
    )
    description: str
    fields: list[FieldSpec] = Field(min_length=1)
    examples: list[dict] = Field(default_factory=list, description="Example entity instances")
    neo4j_label: str | None = Field(None, description="Optional mapping to graph label")


class RelationshipSpec(BaseModel):
    """Relationship between entities."""

    name: str
    source_entity: str
    target_entity: str
    relationship_type: str = Field(..., description="Neo4j relationship type")
    attributes: list[FieldSpec] = Field(default_factory=list)
    directionality: Literal["directed", "bidirectional"] = "directed"


class SentimentScale(StrEnum):
    """Types of sentiment scales to track."""

    POSITIVE_NEGATIVE = "positive_negative"
    SATISFACTION = "satisfaction"
    URGENCY = "urgency"
    CONFIDENCE = "confidence"


class SentimentSpec(BaseModel):
    """Sentiment to track during interviews."""

    topic: str
    scale: SentimentScale
    description: str | None = None


class ExtractionSpec(BaseModel):
    """Complete extraction specification for an agent."""

    entities: list[EntitySpec] = Field(min_length=1)
    relationships: list[RelationshipSpec] = Field(default_factory=list)
    sentiments: list[SentimentSpec] = Field(default_factory=list)
