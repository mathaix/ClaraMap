"""Project context models for Interview Blueprint."""

from pydantic import BaseModel, Field


class SourceContext(BaseModel):
    """Context gathered from MCP integrations (Jira, Confluence, etc.)."""

    jira_projects: list[str] = Field(default_factory=list)
    confluence_spaces: list[str] = Field(default_factory=list)
    key_documents: list[dict] = Field(
        default_factory=list,
        description="List of {name, path, summary} for relevant documents",
    )
    org_context: dict = Field(
        default_factory=dict, description="Organizational context information"
    )
    existing_knowledge: list[dict] = Field(
        default_factory=list, description="Prior knowledge relevant to the project"
    )
    open_questions: list[str] = Field(
        default_factory=list, description="Questions that emerged from source analysis"
    )


class ProjectContext(BaseModel):
    """Project-level context for the interview initiative."""

    name: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., description="Project type from ProjectType enum")
    description: str = Field(..., min_length=10, max_length=5000)
    business_context: str = Field(..., description="Why this project exists")
    decision_to_inform: str = Field(..., description="What decisions will this project inform")
    stakeholders: list[str] = Field(default_factory=list)
    timeline: str | None = Field(None, description="Project timeline description")
    constraints: list[str] = Field(
        default_factory=list, description="Project constraints and limitations"
    )
    source_context: SourceContext = Field(default_factory=SourceContext)
