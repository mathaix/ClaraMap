"""Interview Blueprint Schema Models.

The Interview Blueprint is a comprehensive specification that drives all
downstream Clara systems. It defines how interviews should be conducted,
what entities to extract, and how to synthesize findings.
"""

from clara.models.blueprint.agent import (
    AgentBlueprint,
    AgentConfig,
    DesignRationale,
    GoalSpec,
    IntervieweeSpec,
    PersonaSpec,
    QuestionCategory,
    QuestionFlowSpec,
    QuestionSpec,
)
from clara.models.blueprint.analysis import (
    AnalysisBlueprint,
    DeliverableSpec,
    MetricSpec,
    ReportTemplate,
)
from clara.models.blueprint.core import (
    BlueprintMetadata,
    BlueprintStatus,
    InterviewBlueprint,
    ProjectType,
)
from clara.models.blueprint.extraction import (
    EntitySpec,
    ExtractionSpec,
    FieldSpec,
    FieldType,
    RelationshipSpec,
    SentimentScale,
    SentimentSpec,
)
from clara.models.blueprint.integrations import IntegrationSpec
from clara.models.blueprint.project import ProjectContext, SourceContext
from clara.models.blueprint.quality import QualitySpec, TestScenario
from clara.models.blueprint.synthesis import (
    AnalysisFramework,
    ConflictResolutionSpec,
    CorrelationRule,
    MergeStrategy,
    ResolutionRule,
    SynthesisBlueprint,
)

__all__ = [
    # Core
    "BlueprintMetadata",
    "BlueprintStatus",
    "InterviewBlueprint",
    "ProjectType",
    # Project
    "ProjectContext",
    "SourceContext",
    # Agent
    "AgentBlueprint",
    "AgentConfig",
    "DesignRationale",
    "GoalSpec",
    "IntervieweeSpec",
    "PersonaSpec",
    "QuestionCategory",
    "QuestionFlowSpec",
    "QuestionSpec",
    # Extraction
    "EntitySpec",
    "ExtractionSpec",
    "FieldSpec",
    "FieldType",
    "RelationshipSpec",
    "SentimentScale",
    "SentimentSpec",
    # Synthesis
    "AnalysisFramework",
    "ConflictResolutionSpec",
    "CorrelationRule",
    "MergeStrategy",
    "ResolutionRule",
    "SynthesisBlueprint",
    # Analysis
    "AnalysisBlueprint",
    "DeliverableSpec",
    "MetricSpec",
    "ReportTemplate",
    # Quality
    "QualitySpec",
    "TestScenario",
    # Integrations
    "IntegrationSpec",
]
