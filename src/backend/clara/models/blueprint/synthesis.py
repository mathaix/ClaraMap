"""Synthesis rules models for Interview Blueprint."""

from enum import StrEnum

from pydantic import BaseModel, Field


class MergeStrategy(StrEnum):
    """Strategies for merging duplicate entities."""

    FIRST = "first"
    MOST_RECENT = "most_recent"
    MOST_CONFIDENT = "most_confident"
    MANUAL = "manual"


class ResolutionRule(BaseModel):
    """Rule for resolving entities across interviews."""

    entity_type: str
    matching_fields: list[str] = Field(..., description="Fields to use for matching entities")
    similarity_threshold: float = Field(
        ge=0.0, le=1.0, default=0.8, description="Minimum similarity for match"
    )
    merge_strategy: MergeStrategy = MergeStrategy.MOST_CONFIDENT


class CorrelationRule(BaseModel):
    """Rule for correlating findings across interviews."""

    name: str
    description: str
    entities_involved: list[str]
    correlation_logic: str = Field(..., description="Description of how to correlate")
    output_type: str = Field(..., description="Type of output entity/insight")
    min_occurrences: int = Field(
        ge=1, default=2, description="Minimum mentions to form correlation"
    )


class AnalysisFramework(BaseModel):
    """Analysis framework to apply to correlated data."""

    name: str
    description: str
    inputs: list[str] = Field(..., description="Entity types needed for analysis")
    algorithm: str = Field(..., description="Description of analysis approach")
    output_schema: dict = Field(..., description="Schema for analysis output")
    visualization: str | None = Field(None, description="Suggested visualization type")


class ConflictResolutionSpec(BaseModel):
    """How to handle conflicting information."""

    detection_rules: list[str] = Field(..., description="Rules for detecting conflicts")
    resolution_strategies: list[dict] = Field(..., description="Strategies for resolving conflicts")
    escalation_threshold: float = Field(
        ge=0.0, le=1.0, default=0.3, description="Conflict severity threshold for escalation"
    )
    require_human_review: bool = True


class SynthesisBlueprint(BaseModel):
    """Complete synthesis specification for the blueprint."""

    entity_resolution_rules: list[ResolutionRule] = Field(default_factory=list)
    correlation_rules: list[CorrelationRule] = Field(default_factory=list)
    analysis_frameworks: list[AnalysisFramework] = Field(default_factory=list)
    conflict_resolution: ConflictResolutionSpec | None = None
