"""Analysis blueprint models for Interview Blueprint."""

from pydantic import BaseModel, Field


class DeliverableSpec(BaseModel):
    """Specification for a project deliverable."""

    name: str
    description: str
    format: str = Field(..., description="Output format (report, presentation, etc.)")
    required_data: list[str] = Field(..., description="Entity types required for this deliverable")
    template: str | None = Field(None, description="Template reference")


class MetricSpec(BaseModel):
    """Success metric specification."""

    name: str
    description: str
    calculation: str = Field(..., description="How to calculate this metric")
    target_value: str | None = Field(None, description="Target value if applicable")
    data_sources: list[str] = Field(..., description="Entity types used")


class ReportTemplate(BaseModel):
    """Template for generated reports."""

    name: str
    description: str
    sections: list[dict] = Field(
        ..., description="Report sections with {title, content_type, data_sources}"
    )
    format: str = Field(default="markdown", description="Output format")


class AnalysisBlueprint(BaseModel):
    """Complete analysis specification for the blueprint."""

    deliverables: list[DeliverableSpec] = Field(default_factory=list)
    success_metrics: list[MetricSpec] = Field(default_factory=list)
    report_templates: list[ReportTemplate] = Field(default_factory=list)
