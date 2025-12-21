"""SQLAlchemy ORM models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class ProjectStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class InterviewSessionStatus(str, Enum):
    INVITED = "invited"
    IN_PROGRESS = "in_progress"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class Project(Base):
    """Project - container for discovery initiatives."""

    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_name", "name"),
        Index("ix_projects_status", "status"),
        Index("ix_projects_deleted_at", "deleted_at"),
        Index("ix_projects_created_by", "created_by"),
    )

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ProjectStatus.DRAFT.value)

    timeline_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    timeline_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[str] = mapped_column(String(30), nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    templates: Mapped[list["InterviewTemplate"]] = relationship(back_populates="project")


class InterviewTemplate(Base):
    """Interview Template - reusable agent configuration."""

    __tablename__ = "interview_templates"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    version: Mapped[str] = mapped_column(String(20), default="1.0.0")

    # Template scope
    is_public: Mapped[bool] = mapped_column(Boolean, default=False)
    project_id: Mapped[str | None] = mapped_column(ForeignKey("projects.id"))
    source_template_id: Mapped[str | None] = mapped_column(
        ForeignKey("interview_templates.id")
    )

    # Agent configuration
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    persona: Mapped[dict] = mapped_column(JSON, default=dict)
    questions: Mapped[list[dict]] = mapped_column(JSON, default=list)
    extraction_schema: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_by: Mapped[str] = mapped_column(String(30), nullable=False)

    # Relationships
    project: Mapped[Optional["Project"]] = relationship(back_populates="templates")
    source_template: Mapped[Optional["InterviewTemplate"]] = relationship(remote_side=[id])
    agents: Mapped[list["Agent"]] = relationship(back_populates="template")


class Agent(Base):
    """Agent - an AI interviewer instance configured from a template."""

    __tablename__ = "agents"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    template_id: Mapped[str] = mapped_column(ForeignKey("interview_templates.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    # Runtime configuration (can override template settings)
    config_overrides: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    template: Mapped["InterviewTemplate"] = relationship(back_populates="agents")
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(back_populates="agent")


class Interviewee(Base):
    """Interviewee - person being interviewed."""

    __tablename__ = "interviewees"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str | None] = mapped_column(String(100))
    role: Mapped[str | None] = mapped_column(String(100))
    department: Mapped[str | None] = mapped_column(String(100))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    interview_sessions: Mapped[list["InterviewSession"]] = relationship(
        back_populates="interviewee"
    )


class DesignPhase(str, Enum):
    """Design session phases."""
    GOAL_UNDERSTANDING = "goal_understanding"
    AGENT_CONFIGURATION = "agent_configuration"
    BLUEPRINT_DESIGN = "blueprint_design"
    COMPLETE = "complete"


class DesignSessionStatus(str, Enum):
    """Design session statuses."""
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class DesignSession(Base):
    """Design Session - tracks blueprint design conversation state.

    Persists the full state of a design assistant session so users can
    resume where they left off.
    """

    __tablename__ = "design_sessions"
    __table_args__ = (
        Index("ix_design_sessions_project_id", "project_id"),
        Index("ix_design_sessions_status", "status"),
    )

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=DesignSessionStatus.ACTIVE.value)

    # Current phase in the design flow
    phase: Mapped[str] = mapped_column(String(30), default=DesignPhase.GOAL_UNDERSTANDING.value)

    # Conversation history - list of {role: "user"|"assistant", content: str}
    messages: Mapped[list[dict]] = mapped_column(JSON, default=list)

    # Blueprint state - accumulated from tool calls
    blueprint_state: Mapped[dict] = mapped_column(JSON, default=dict)
    # Structure: {
    #   "project": {"name": str, "type": str, "domain": str, "description": str},
    #   "entities": [{"name": str, "attributes": list, "description": str}],
    #   "agents": [{"name": str, "persona": str, "topics": list, "tone": str}],
    # }

    # Goal summary from Phase 1
    goal_summary: Mapped[dict | None] = mapped_column(JSON)

    # Agent capabilities from Phase 2
    agent_capabilities: Mapped[dict | None] = mapped_column(JSON)

    # Metrics
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    message_count: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DesignSessionPrompt(Base):
    """Hydrated prompt for a design session phase."""

    __tablename__ = "design_session_prompts"
    __table_args__ = (
        Index("ix_design_session_prompts_session_phase", "session_id", "phase"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(50), ForeignKey("design_sessions.id"), nullable=False)
    phase: Mapped[str] = mapped_column(String(30), nullable=False)
    template_name: Mapped[str] = mapped_column(String(100), nullable=False)
    hydrated_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    context_data: Mapped[dict] = mapped_column(JSON, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationship
    session: Mapped["DesignSession"] = relationship()


class InterviewSession(Base):
    """Interview Session - pairs an Agent with an Interviewee for a Project."""

    __tablename__ = "interview_sessions"

    id: Mapped[str] = mapped_column(String(30), primary_key=True)
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id"), nullable=False)
    agent_id: Mapped[str] = mapped_column(ForeignKey("agents.id"), nullable=False)
    interviewee_id: Mapped[str] = mapped_column(ForeignKey("interviewees.id"), nullable=False)

    status: Mapped[str] = mapped_column(String(20), default=InterviewSessionStatus.INVITED.value)

    # Invitation
    invite_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    invite_expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    invite_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Interview data
    transcript: Mapped[list[dict]] = mapped_column(JSON, default=list)
    summary: Mapped[str | None] = mapped_column(Text)
    extracted_entities: Mapped[list[dict]] = mapped_column(JSON, default=list)
    topic_coverage: Mapped[dict] = mapped_column(JSON, default=dict)

    # Metrics
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    project: Mapped["Project"] = relationship(back_populates="interview_sessions")
    agent: Mapped["Agent"] = relationship(back_populates="interview_sessions")
    interviewee: Mapped["Interviewee"] = relationship(back_populates="interview_sessions")
