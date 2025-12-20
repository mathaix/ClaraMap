"""Quality specification models for Interview Blueprint."""

from pydantic import BaseModel, Field


class TestScenario(BaseModel):
    """Test scenario for validating agent behavior."""

    name: str
    description: str
    persona_type: str = Field(
        ..., description="Type of test persona (cooperative, reluctant, etc.)"
    )
    expected_behavior: str = Field(..., description="Expected agent behavior")
    ground_truth: dict = Field(default_factory=dict, description="Ground truth entities to extract")
    evaluation_criteria: list[str] = Field(
        default_factory=list, description="Criteria for evaluating success"
    )


class QualitySpec(BaseModel):
    """Quality thresholds and testing configuration."""

    interview_quality_thresholds: dict[str, float] = Field(
        default_factory=lambda: {
            "min_coverage": 0.7,
            "min_depth": 0.6,
            "min_rapport": 0.5,
        },
        description="Minimum quality thresholds for interviews",
    )
    extraction_quality_thresholds: dict[str, float] = Field(
        default_factory=lambda: {
            "min_precision": 0.8,
            "min_recall": 0.7,
            "min_confidence": 0.6,
        },
        description="Minimum quality thresholds for extraction",
    )
    coverage_requirements: dict[str, int] = Field(
        default_factory=dict,
        description="Minimum entity counts per type",
    )
    test_scenarios: list[TestScenario] = Field(default_factory=list)
