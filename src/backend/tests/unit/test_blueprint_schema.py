"""Unit tests for Interview Blueprint schema models."""

import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from clara.models.blueprint import (
    AgentBlueprint,
    AgentConfig,
    BlueprintMetadata,
    BlueprintStatus,
    EntitySpec,
    ExtractionSpec,
    FieldSpec,
    FieldType,
    GoalSpec,
    InterviewBlueprint,
    IntervieweeSpec,
    PersonaSpec,
    ProjectContext,
    ProjectType,
    QuestionCategory,
    QuestionFlowSpec,
    QuestionSpec,
    SourceContext,
)


class TestProjectContext:
    """Tests for ProjectContext model."""

    def test_valid_project_context(self):
        """Test creating a valid project context."""
        ctx = ProjectContext(
            name="ERP Discovery Project",
            type=ProjectType.ERP_DISCOVERY,
            description="Discover current ERP usage and pain points across the organization",
            business_context="Planning to migrate from legacy systems",
            decision_to_inform="ERP vendor selection and implementation approach",
            stakeholders=["CIO", "CFO", "IT Director"],
        )
        assert ctx.name == "ERP Discovery Project"
        assert ctx.type == ProjectType.ERP_DISCOVERY

    def test_project_context_with_source_context(self):
        """Test project context with MCP source data."""
        ctx = ProjectContext(
            name="Due Diligence Project",
            type=ProjectType.MA_DUE_DILIGENCE,
            description="Technical due diligence for acquisition target",
            business_context="Evaluating acquisition target",
            decision_to_inform="Go/no-go acquisition decision",
            source_context=SourceContext(
                jira_projects=["TECH", "OPS"],
                confluence_spaces=["Engineering", "Operations"],
                key_documents=[{"name": "Tech Stack", "path": "/docs/tech-stack.md"}],
            ),
        )
        assert len(ctx.source_context.jira_projects) == 2

    def test_project_context_description_min_length(self):
        """Test that description must be at least 10 characters."""
        with pytest.raises(ValidationError) as exc_info:
            ProjectContext(
                name="Test",
                type=ProjectType.CUSTOM,
                description="Short",  # Too short
                business_context="Test",
                decision_to_inform="Test",
            )
        assert "String should have at least 10 characters" in str(exc_info.value)


class TestAgentBlueprint:
    """Tests for AgentBlueprint model."""

    def create_minimal_agent(self) -> AgentBlueprint:
        """Create a minimal valid agent blueprint for testing."""
        return AgentBlueprint(
            id="agent_abc12345",
            name="Technical Discovery Agent",
            description="Interviews technical staff about systems and processes",
            target_interviewees=IntervieweeSpec(
                roles=["Developer", "Architect"],
                departments=["Engineering"],
                count_target=10,
            ),
            persona=PersonaSpec(
                role="Senior Technical Consultant",
                tone="Professional but approachable",
                expertise=["Software Architecture", "Cloud Systems"],
                communication_style="Clear and concise",
                rapport_building_approach="Start with their background",
                handling_reluctance="Acknowledge concerns, explain value",
            ),
            goals=[
                GoalSpec(
                    id="goal_abc12345",
                    goal="Understand current system architecture and integrations",
                    priority=1,
                    success_criteria=["Identify all major systems", "Map integrations"],
                )
            ],
            questions=[
                QuestionSpec(
                    id="q_rapp0001",
                    question="Can you tell me about your role and what systems you work with?",
                    purpose="Build rapport and understand context",
                    category=QuestionCategory.RAPPORT,
                    sequence_position=1,
                ),
                QuestionSpec(
                    id="q_disc0001",
                    question="What are the main systems you interact with daily?",
                    purpose="Discover key systems",
                    category=QuestionCategory.DISCOVERY,
                    sequence_position=2,
                    expected_entities=["System"],
                ),
                QuestionSpec(
                    id="q_clos0001",
                    question="Is there anything else you'd like to share about your experience?",
                    purpose="Closing question",
                    category=QuestionCategory.CLOSING,
                    sequence_position=3,
                ),
            ],
            question_flow=QuestionFlowSpec(
                opening_sequence=["q_rapp0001"],
                core_sequence=["q_disc0001"],
                closing_sequence=["q_clos0001"],
            ),
            extraction=ExtractionSpec(
                entities=[
                    EntitySpec(
                        name="System",
                        description="A software system or application",
                        fields=[
                            FieldSpec(
                                name="name",
                                type=FieldType.STRING,
                                required=True,
                                description="System name",
                            ),
                            FieldSpec(
                                name="vendor",
                                type=FieldType.STRING,
                                required=False,
                                description="System vendor",
                            ),
                        ],
                    )
                ]
            ),
        )

    def test_valid_agent_blueprint(self):
        """Test creating a valid agent blueprint."""
        agent = self.create_minimal_agent()
        assert agent.name == "Technical Discovery Agent"
        assert len(agent.goals) == 1
        assert len(agent.questions) == 3

    def test_agent_id_pattern(self):
        """Test that agent ID must match pattern."""
        with pytest.raises(ValidationError) as exc_info:
            AgentBlueprint(
                id="invalid_id",  # Doesn't match pattern
                name="Test Agent",
                description="Test",
                target_interviewees=IntervieweeSpec(count_target=5),
                persona=PersonaSpec(
                    role="Test",
                    tone="Test",
                    expertise=["Test"],
                    communication_style="Test",
                    rapport_building_approach="Test",
                    handling_reluctance="Test",
                ),
                goals=[
                    GoalSpec(
                        id="goal_12345678",
                        goal="Test goal here",
                        priority=1,
                        success_criteria=["Test"],
                    )
                ],
                questions=[
                    QuestionSpec(
                        id="q_12345678",
                        question="Test question here?",
                        purpose="Test",
                        category=QuestionCategory.DISCOVERY,
                        sequence_position=1,
                    )
                ],
                question_flow=QuestionFlowSpec(
                    opening_sequence=["q_12345678"],
                    core_sequence=["q_12345678"],
                    closing_sequence=["q_12345678"],
                ),
                extraction=ExtractionSpec(
                    entities=[
                        EntitySpec(
                            name="Test",
                            description="Test",
                            fields=[
                                FieldSpec(
                                    name="field",
                                    type=FieldType.STRING,
                                    description="Test",
                                )
                            ],
                        )
                    ]
                ),
            )
        assert "String should match pattern" in str(exc_info.value)

    def test_agent_config_defaults(self):
        """Test that agent config has sensible defaults."""
        agent = self.create_minimal_agent()
        assert agent.config.model == "claude-sonnet-4-20250514"
        assert agent.config.max_turns == 50
        assert agent.config.target_duration_minutes == 30

    def test_custom_agent_config(self):
        """Test overriding agent config."""
        config = AgentConfig(
            model="claude-3-5-haiku-20241022",
            max_turns=30,
            target_duration_minutes=20,
            temperature=0.5,
        )
        assert config.model == "claude-3-5-haiku-20241022"
        assert config.max_turns == 30


class TestExtractionSpec:
    """Tests for ExtractionSpec model."""

    def test_entity_name_pattern(self):
        """Test that entity names must be PascalCase."""
        with pytest.raises(ValidationError):
            EntitySpec(
                name="invalid_name",  # Should be PascalCase
                description="Test",
                fields=[
                    FieldSpec(name="test", type=FieldType.STRING, description="Test")
                ],
            )

    def test_field_name_pattern(self):
        """Test that field names must be snake_case."""
        with pytest.raises(ValidationError):
            FieldSpec(
                name="InvalidName",  # Should be snake_case
                type=FieldType.STRING,
                description="Test",
            )

    def test_valid_extraction_spec(self):
        """Test creating a valid extraction spec."""
        spec = ExtractionSpec(
            entities=[
                EntitySpec(
                    name="Person",
                    description="A person in the organization",
                    fields=[
                        FieldSpec(
                            name="name",
                            type=FieldType.STRING,
                            required=True,
                            description="Person's name",
                        ),
                        FieldSpec(
                            name="role",
                            type=FieldType.STRING,
                            required=False,
                            description="Person's role",
                        ),
                    ],
                    examples=[{"name": "John Doe", "role": "Developer"}],
                ),
                EntitySpec(
                    name="System",
                    description="A software system",
                    fields=[
                        FieldSpec(
                            name="name",
                            type=FieldType.STRING,
                            required=True,
                            description="System name",
                        ),
                    ],
                ),
            ]
        )
        assert len(spec.entities) == 2


class TestInterviewBlueprint:
    """Tests for complete InterviewBlueprint model."""

    def create_minimal_blueprint(self) -> InterviewBlueprint:
        """Create a minimal valid blueprint for testing."""
        now = datetime.now(timezone.utc)

        return InterviewBlueprint(
            metadata=BlueprintMetadata(
                id="bp_1234567890abcdef",
                version="1.0.0",
                status=BlueprintStatus.DRAFT,
                created_at=now,
                updated_at=now,
                created_by="user_123",
                project_id="proj_1234567890abcdef",
            ),
            project=ProjectContext(
                name="Test Discovery Project",
                type=ProjectType.ERP_DISCOVERY,
                description="Test project for unit testing the blueprint schema",
                business_context="Testing the blueprint implementation",
                decision_to_inform="Validation of the schema design",
            ),
            agents=[
                AgentBlueprint(
                    id="agent_12345678",
                    name="Test Agent",
                    description="Test agent for validation",
                    target_interviewees=IntervieweeSpec(count_target=5),
                    persona=PersonaSpec(
                        role="Consultant",
                        tone="Professional",
                        expertise=["Testing"],
                        communication_style="Clear",
                        rapport_building_approach="Friendly",
                        handling_reluctance="Patient",
                    ),
                    goals=[
                        GoalSpec(
                            id="goal_12345678",
                            goal="Validate blueprint schema",
                            priority=1,
                            success_criteria=["All tests pass"],
                        )
                    ],
                    questions=[
                        QuestionSpec(
                            id="q_12345678",
                            question="What is your experience with the system?",
                            purpose="Discovery",
                            category=QuestionCategory.DISCOVERY,
                            sequence_position=1,
                        )
                    ],
                    question_flow=QuestionFlowSpec(
                        opening_sequence=["q_12345678"],
                        core_sequence=["q_12345678"],
                        closing_sequence=["q_12345678"],
                    ),
                    extraction=ExtractionSpec(
                        entities=[
                            EntitySpec(
                                name="System",
                                description="A system",
                                fields=[
                                    FieldSpec(
                                        name="name",
                                        type=FieldType.STRING,
                                        description="Name",
                                    )
                                ],
                            )
                        ]
                    ),
                )
            ],
        )

    def test_valid_blueprint(self):
        """Test creating a valid blueprint."""
        blueprint = self.create_minimal_blueprint()
        assert blueprint.metadata.version == "1.0.0"
        assert len(blueprint.agents) == 1

    def test_blueprint_requires_at_least_one_agent(self):
        """Test that blueprint requires at least one agent."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValidationError) as exc_info:
            InterviewBlueprint(
                metadata=BlueprintMetadata(
                    id="bp_1234567890abcdef",
                    version="1.0.0",
                    created_at=now,
                    updated_at=now,
                    created_by="user_123",
                    project_id="proj_1234567890abcdef",
                ),
                project=ProjectContext(
                    name="Test Project",
                    type=ProjectType.CUSTOM,
                    description="Test project description",
                    business_context="Test",
                    decision_to_inform="Test",
                ),
                agents=[],  # Empty list should fail
            )
        assert "List should have at least 1 item" in str(exc_info.value)

    def test_blueprint_json_serialization(self):
        """Test that blueprint can be serialized to and from JSON."""
        blueprint = self.create_minimal_blueprint()

        # Serialize to JSON
        json_str = blueprint.model_dump_json()

        # Parse the JSON
        data = json.loads(json_str)

        # Deserialize back to model
        restored = InterviewBlueprint.model_validate(data)

        assert restored.metadata.id == blueprint.metadata.id
        assert restored.project.name == blueprint.project.name
        assert len(restored.agents) == len(blueprint.agents)

    def test_get_agent_by_id(self):
        """Test getting an agent by ID."""
        blueprint = self.create_minimal_blueprint()
        agent = blueprint.get_agent("agent_12345678")
        assert agent is not None
        assert agent.name == "Test Agent"

        missing = blueprint.get_agent("agent_nonexistent")
        assert missing is None

    def test_get_all_entity_types(self):
        """Test getting all entity types across agents."""
        blueprint = self.create_minimal_blueprint()
        entity_types = blueprint.get_all_entity_types()
        assert "System" in entity_types

    def test_blueprint_version_pattern(self):
        """Test that version must match semver pattern."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValidationError):
            BlueprintMetadata(
                id="bp_1234567890abcdef",
                version="v1.0",  # Invalid format
                created_at=now,
                updated_at=now,
                created_by="user_123",
                project_id="proj_1234567890abcdef",
            )


class TestQuestionSpec:
    """Tests for QuestionSpec model."""

    def test_question_categories(self):
        """Test all question categories are valid."""
        categories = [
            QuestionCategory.RAPPORT,
            QuestionCategory.DISCOVERY,
            QuestionCategory.PROBING,
            QuestionCategory.SENSITIVE,
            QuestionCategory.CLOSING,
        ]
        for cat in categories:
            q = QuestionSpec(
                id="q_12345678",
                question="Test question for category?",
                purpose="Testing category",
                category=cat,
                sequence_position=1,
            )
            assert q.category == cat

    def test_question_with_follow_ups(self):
        """Test question with follow-up questions."""
        q = QuestionSpec(
            id="q_12345678",
            question="What systems do you use daily?",
            purpose="Discover systems",
            category=QuestionCategory.DISCOVERY,
            sequence_position=1,
            probing_triggers=["mentions pain point", "seems unsure"],
            follow_up_questions=[
                "Can you tell me more about that?",
                "What challenges have you faced?",
            ],
            expected_entities=["System", "PainPoint"],
        )
        assert len(q.follow_up_questions) == 2
        assert len(q.expected_entities) == 2
