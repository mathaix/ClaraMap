"""Core Interview Blueprint models."""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from clara.models.blueprint.agent import AgentBlueprint
from clara.models.blueprint.analysis import AnalysisBlueprint
from clara.models.blueprint.integrations import IntegrationSpec
from clara.models.blueprint.project import ProjectContext
from clara.models.blueprint.quality import QualitySpec
from clara.models.blueprint.synthesis import SynthesisBlueprint


class ProjectType(StrEnum):
    """Supported project types with specialized templates."""

    MA_DUE_DILIGENCE = "ma_due_diligence"
    ERP_DISCOVERY = "erp_discovery"
    PROCESS_OPTIMIZATION = "process_optimization"
    COMPLIANCE_AUDIT = "compliance_audit"
    KNOWLEDGE_CAPTURE = "knowledge_capture"
    VENDOR_ASSESSMENT = "vendor_assessment"
    CUSTOMER_RESEARCH = "customer_research"
    CUSTOM = "custom"


class BlueprintStatus(StrEnum):
    """Blueprint lifecycle status."""

    DRAFT = "draft"
    REVIEW = "review"
    APPROVED = "approved"
    ACTIVE = "active"
    ARCHIVED = "archived"


class BlueprintMetadata(BaseModel):
    """Blueprint identification and versioning."""

    id: str = Field(..., pattern=r"^bp_[a-z0-9]{16}$")
    version: str = Field(..., pattern=r"^\d+\.\d+\.\d+$")
    status: BlueprintStatus = BlueprintStatus.DRAFT
    created_at: datetime
    updated_at: datetime
    created_by: str = Field(..., description="Manager who created/approved")
    designed_by: str = Field(default="opus", description="AI that designed it")
    project_id: str = Field(..., pattern=r"^proj_[a-z0-9]{16}$")


class InterviewBlueprint(BaseModel):
    """Complete Interview Blueprint specification.

    The Interview Blueprint is the comprehensive specification that drives all
    downstream Clara systems. It defines:
    - Project context and goals
    - Agent configurations for different interviewee groups
    - Entity extraction schemas
    - Synthesis rules for combining findings
    - Quality thresholds and testing
    - Integration configurations
    """

    metadata: BlueprintMetadata

    # Project context
    project: ProjectContext

    # Agent definitions (supports multiple agents for different interviewee groups)
    agents: list[AgentBlueprint] = Field(min_length=1, description="At least one agent required")

    # Synthesis configuration
    synthesis: SynthesisBlueprint = Field(default_factory=SynthesisBlueprint)

    # Analysis configuration
    analysis: AnalysisBlueprint = Field(default_factory=AnalysisBlueprint)

    # Quality specifications
    quality: QualitySpec = Field(default_factory=QualitySpec)

    # External integrations
    integrations: IntegrationSpec = Field(default_factory=IntegrationSpec)

    def get_agent(self, agent_id: str) -> AgentBlueprint | None:
        """Get an agent by ID."""
        for agent in self.agents:
            if agent.id == agent_id:
                return agent
        return None

    def get_all_entity_types(self) -> set[str]:
        """Get all unique entity types across all agents."""
        entity_types: set[str] = set()
        for agent in self.agents:
            for entity in agent.extraction.entities:
                entity_types.add(entity.name)
        return entity_types

    def get_all_relationship_types(self) -> set[str]:
        """Get all unique relationship types across all agents."""
        rel_types: set[str] = set()
        for agent in self.agents:
            for rel in agent.extraction.relationships:
                rel_types.add(rel.relationship_type)
        return rel_types
