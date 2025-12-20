"""Unit tests for blueprint validation service."""

from datetime import UTC, datetime

from clara.models.blueprint import (
    AgentBlueprint,
    AgentConfig,
    BlueprintMetadata,
    BlueprintStatus,
    DesignRationale,
    EntitySpec,
    ExtractionSpec,
    FieldSpec,
    FieldType,
    GoalSpec,
    InterviewBlueprint,
    IntervieweeSpec,
    PersonaSpec,
    ProjectContext,
    QuestionCategory,
    QuestionFlowSpec,
    QuestionSpec,
    SentimentScale,
    SentimentSpec,
)
from clara.services.blueprint_validation import (
    BlueprintValidator,
    ValidationSeverity,
    validate_blueprint,
)


def create_test_question(
    id: str,
    category: QuestionCategory = QuestionCategory.DISCOVERY,
    sequence: int = 1,
    probing_triggers: list[str] | None = None,
    follow_up_questions: list[str] | None = None,
    skip_conditions: list[str] | None = None,
    expected_entities: list[str] | None = None,
) -> QuestionSpec:
    """Create a test question with defaults."""
    return QuestionSpec(
        id=id,
        question="This is a test question for the interview",
        purpose="Testing",
        category=category,
        sequence_position=sequence,
        probing_triggers=probing_triggers or [],
        follow_up_questions=follow_up_questions or [],
        skip_conditions=skip_conditions or [],
        expected_entities=expected_entities or [],
    )


def create_minimal_blueprint(
    questions: list[QuestionSpec] | None = None,
    question_flow: QuestionFlowSpec | None = None,
    goals: list[GoalSpec] | None = None,
    entities: list[EntitySpec] | None = None,
    include_design_rationale: bool = True,
    include_sentiments: bool = True,
) -> InterviewBlueprint:
    """Create a minimal valid blueprint for testing."""
    if questions is None:
        questions = [
            create_test_question(
                "q_rapp0001",
                QuestionCategory.RAPPORT,
                1,
                probing_triggers=["if they seem hesitant"],
                follow_up_questions=["Can you elaborate?"],
            ),
            create_test_question(
                "q_disc0001",
                QuestionCategory.DISCOVERY,
                2,
                probing_triggers=["mention of challenges"],
                follow_up_questions=["What happened next?"],
                expected_entities=["System"],
            ),
            create_test_question(
                "q_clos0001",
                QuestionCategory.CLOSING,
                3,
                skip_conditions=["if time is short"],
            ),
        ]

    if question_flow is None:
        question_flow = QuestionFlowSpec(
            opening_sequence=["q_rapp0001"],
            core_sequence=["q_disc0001"],
            closing_sequence=["q_clos0001"],
        )

    if goals is None:
        goals = [
            GoalSpec(
                id="goal_abc12345",
                goal="Understand the current system landscape",
                priority=1,
                success_criteria=["Identified major systems"],
                related_questions=["q_disc0001"],
            )
        ]

    if entities is None:
        entities = [
            EntitySpec(
                name="System",
                description="A software system",
                fields=[
                    FieldSpec(
                        name="name",
                        type=FieldType.STRING,
                        required=True,
                        description="System name",
                    )
                ],
                examples=[{"name": "ERP System"}],
            )
        ]

    sentiments = []
    if include_sentiments:
        sentiments = [
            SentimentSpec(
                topic="overall_satisfaction",
                scale=SentimentScale.SATISFACTION,
            )
        ]

    design_rationale = None
    if include_design_rationale:
        design_rationale = DesignRationale(
            persona_reasoning="Chosen for technical depth and approachability",
            question_strategy="Progressive disclosure from rapport to deep dive",
            extraction_approach="Entity-first with relationship inference",
            key_considerations=["Build trust early", "Allow tangents"],
        )

    return InterviewBlueprint(
        metadata=BlueprintMetadata(
            id="bp_1234567890abcdef",
            version="1.0.0",
            status=BlueprintStatus.DRAFT,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            created_by="user_test",
            project_id="proj_1234567890abcdef",
        ),
        project=ProjectContext(
            name="Test Project",
            type="erp_discovery",
            description="This is a test project for validation testing",
            business_context="Testing the validation service functionality",
            decision_to_inform="Whether validation is working correctly",
            stakeholders=["Test Team"],
        ),
        agents=[
            AgentBlueprint(
                id="agent_abc12345",
                name="Test Agent",
                description="Agent for testing validation",
                target_interviewees=IntervieweeSpec(
                    roles=["Developer"],
                    count_target=10,
                    selection_criteria="Anyone in engineering department",
                ),
                persona=PersonaSpec(
                    role="Senior Technical Analyst",
                    tone="Professional but friendly and approachable",
                    expertise=["Software Architecture", "Integration"],
                    communication_style="Clear and concise with technical depth when needed",
                    rapport_building_approach="Start with context about the project and their role",
                    handling_reluctance="Acknowledge concerns and explain confidentiality measures",
                ),
                goals=goals,
                questions=questions,
                question_flow=question_flow,
                extraction=ExtractionSpec(
                    entities=entities,
                    sentiments=sentiments,
                ),
                config=AgentConfig(),
                design_rationale=design_rationale,
            )
        ],
    )


class TestBlueprintValidator:
    """Tests for BlueprintValidator."""

    def test_valid_blueprint_passes_validation(self):
        """A well-formed blueprint should pass validation."""
        blueprint = create_minimal_blueprint()
        result = validate_blueprint(blueprint)

        assert result.is_valid is True
        assert result.error_count == 0
        assert result.quality_score >= 0

    def test_invalid_question_ref_in_opening_sequence(self):
        """Invalid question ID in opening sequence should cause error."""
        blueprint = create_minimal_blueprint(
            question_flow=QuestionFlowSpec(
                opening_sequence=["q_nonexist"],  # Invalid ID
                core_sequence=["q_disc0001"],
                closing_sequence=["q_clos0001"],
            )
        )
        result = validate_blueprint(blueprint)

        assert result.is_valid is False
        assert result.error_count >= 1
        errors = [i for i in result.issues if i.severity == ValidationSeverity.ERROR]
        assert any("opening_sequence" in e.path for e in errors)

    def test_invalid_question_ref_in_core_sequence(self):
        """Invalid question ID in core sequence should cause error."""
        blueprint = create_minimal_blueprint(
            question_flow=QuestionFlowSpec(
                opening_sequence=["q_rapp0001"],
                core_sequence=["q_invalid1"],  # Invalid ID
                closing_sequence=["q_clos0001"],
            )
        )
        result = validate_blueprint(blueprint)

        assert result.is_valid is False
        error_codes = [i.code for i in result.issues if i.severity == ValidationSeverity.ERROR]
        assert "INVALID_QUESTION_REF" in error_codes

    def test_invalid_entity_ref_in_question(self):
        """Invalid entity reference in question should cause warning."""
        questions = [
            create_test_question(
                "q_rapp0001",
                QuestionCategory.RAPPORT,
                1,
                expected_entities=["NonExistentEntity"],  # Invalid entity
            ),
            create_test_question("q_disc0001", QuestionCategory.DISCOVERY, 2),
            create_test_question("q_clos0001", QuestionCategory.CLOSING, 3),
        ]
        blueprint = create_minimal_blueprint(questions=questions)
        result = validate_blueprint(blueprint)

        warnings = [i for i in result.issues if i.severity == ValidationSeverity.WARNING]
        assert any("INVALID_ENTITY_REF" == w.code for w in warnings)

    def test_invalid_question_ref_in_goal(self):
        """Invalid question reference in goal should cause warning."""
        goals = [
            GoalSpec(
                id="goal_abc12345",
                goal="Test goal with invalid question reference",
                priority=1,
                success_criteria=["Some criteria"],
                related_questions=["q_nonexist"],  # Invalid question ID
            )
        ]
        blueprint = create_minimal_blueprint(goals=goals)
        result = validate_blueprint(blueprint)

        warnings = [i for i in result.issues if i.severity == ValidationSeverity.WARNING]
        assert any("INVALID_QUESTION_REF_IN_GOAL" == w.code for w in warnings)

    def test_quality_score_in_valid_range(self):
        """Quality score should be between 0 and 100."""
        blueprint = create_minimal_blueprint()
        result = validate_blueprint(blueprint)

        assert 0 <= result.quality_score <= 100

    def test_quality_dimensions_present(self):
        """All quality dimensions should be calculated."""
        blueprint = create_minimal_blueprint()
        result = validate_blueprint(blueprint)

        dimension_names = {d.name for d in result.quality_dimensions}
        expected = {
            "completeness",
            "coherence",
            "question_quality",
            "extraction_coverage",
            "persona_quality",
        }
        assert dimension_names == expected

    def test_quality_weights_sum_to_one(self):
        """Quality dimension weights should sum to 1.0."""
        validator = BlueprintValidator()
        total = sum(validator.WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_ready_for_deployment_with_high_score(self):
        """Blueprint with high quality score should be ready for deployment."""
        blueprint = create_minimal_blueprint()
        result = validate_blueprint(blueprint)

        # If valid and score >= 70, should be ready
        if result.is_valid and result.quality_score >= 70:
            assert result.ready_for_deployment is True

    def test_not_ready_for_deployment_with_errors(self):
        """Blueprint with errors should not be ready for deployment."""
        blueprint = create_minimal_blueprint(
            question_flow=QuestionFlowSpec(
                opening_sequence=["q_invalid1"],
                core_sequence=["q_disc0001"],
                closing_sequence=["q_clos0001"],
            )
        )
        result = validate_blueprint(blueprint)

        assert result.ready_for_deployment is False

    def test_completeness_score_decreases_without_design_rationale(self):
        """Completeness score should be lower without design rationale."""
        with_rationale = create_minimal_blueprint(include_design_rationale=True)
        without_rationale = create_minimal_blueprint(include_design_rationale=False)

        result_with = validate_blueprint(with_rationale)
        result_without = validate_blueprint(without_rationale)

        completeness_with = next(
            d for d in result_with.quality_dimensions if d.name == "completeness"
        )
        completeness_without = next(
            d for d in result_without.quality_dimensions if d.name == "completeness"
        )

        assert completeness_with.score >= completeness_without.score

    def test_extraction_coverage_decreases_without_sentiments(self):
        """Extraction coverage should be lower without sentiment tracking."""
        with_sentiments = create_minimal_blueprint(include_sentiments=True)
        without_sentiments = create_minimal_blueprint(include_sentiments=False)

        result_with = validate_blueprint(with_sentiments)
        result_without = validate_blueprint(without_sentiments)

        extraction_with = next(
            d for d in result_with.quality_dimensions if d.name == "extraction_coverage"
        )
        extraction_without = next(
            d for d in result_without.quality_dimensions if d.name == "extraction_coverage"
        )

        assert extraction_with.score >= extraction_without.score

    def test_question_quality_checks_category_diversity(self):
        """Question quality should be lower without category diversity."""
        # All questions same category
        uniform_questions = [
            create_test_question("q_disc0001", QuestionCategory.DISCOVERY, 1),
            create_test_question("q_disc0002", QuestionCategory.DISCOVERY, 2),
            create_test_question("q_disc0003", QuestionCategory.DISCOVERY, 3),
        ]
        blueprint = create_minimal_blueprint(
            questions=uniform_questions,
            question_flow=QuestionFlowSpec(
                opening_sequence=["q_disc0001"],
                core_sequence=["q_disc0002"],
                closing_sequence=["q_disc0003"],
            ),
        )
        result = validate_blueprint(blueprint)

        question_quality = next(
            d for d in result.quality_dimensions if d.name == "question_quality"
        )
        # Should have issues about missing categories
        assert len(question_quality.issues) > 0

    def test_unused_questions_affect_coherence(self):
        """Questions not in any flow should reduce coherence score."""
        questions = [
            create_test_question("q_rapp0001", QuestionCategory.RAPPORT, 1),
            create_test_question("q_disc0001", QuestionCategory.DISCOVERY, 2),
            create_test_question("q_clos0001", QuestionCategory.CLOSING, 3),
            create_test_question("q_unus0001", QuestionCategory.DISCOVERY, 4),  # Not in flow
        ]
        blueprint = create_minimal_blueprint(
            questions=questions,
            question_flow=QuestionFlowSpec(
                opening_sequence=["q_rapp0001"],
                core_sequence=["q_disc0001"],
                closing_sequence=["q_clos0001"],
            ),
        )
        result = validate_blueprint(blueprint)

        coherence = next(d for d in result.quality_dimensions if d.name == "coherence")
        assert any("not in any flow" in issue for issue in coherence.issues)

    def test_entity_without_required_fields_affects_extraction_coverage(self):
        """Entity without required fields should reduce extraction coverage."""
        entities = [
            EntitySpec(
                name="WeakEntity",
                description="Entity with no required fields",
                fields=[
                    FieldSpec(
                        name="optional_field",
                        type=FieldType.STRING,
                        required=False,  # No required fields
                        description="Optional field",
                    )
                ],
            )
        ]
        blueprint = create_minimal_blueprint(entities=entities)
        result = validate_blueprint(blueprint)

        extraction = next(d for d in result.quality_dimensions if d.name == "extraction_coverage")
        assert any("No required fields" in issue for issue in extraction.issues)

    def test_weighted_score_calculation(self):
        """Weighted score should be score * weight."""
        blueprint = create_minimal_blueprint()
        result = validate_blueprint(blueprint)

        for dim in result.quality_dimensions:
            expected = dim.score * dim.weight
            assert abs(dim.weighted_score - expected) < 0.01

    def test_error_and_warning_counts(self):
        """Error and warning counts should match issues list."""
        blueprint = create_minimal_blueprint(
            question_flow=QuestionFlowSpec(
                opening_sequence=["q_invalid1"],  # Error
                core_sequence=["q_disc0001"],
                closing_sequence=["q_clos0001"],
            )
        )
        result = validate_blueprint(blueprint)

        actual_errors = sum(1 for i in result.issues if i.severity == ValidationSeverity.ERROR)
        actual_warnings = sum(1 for i in result.issues if i.severity == ValidationSeverity.WARNING)

        assert result.error_count == actual_errors
        assert result.warning_count == actual_warnings


class TestValidationIssues:
    """Tests for specific validation issue detection."""

    def test_issue_includes_agent_id(self):
        """Validation issues should include agent ID when applicable."""
        blueprint = create_minimal_blueprint(
            question_flow=QuestionFlowSpec(
                opening_sequence=["q_invalid1"],
                core_sequence=["q_disc0001"],
                closing_sequence=["q_clos0001"],
            )
        )
        result = validate_blueprint(blueprint)

        agent_issues = [i for i in result.issues if i.agent_id is not None]
        assert len(agent_issues) > 0
        assert agent_issues[0].agent_id == "agent_abc12345"

    def test_issue_includes_path(self):
        """Validation issues should include path to the problem."""
        blueprint = create_minimal_blueprint(
            question_flow=QuestionFlowSpec(
                opening_sequence=["q_invalid1"],
                core_sequence=["q_disc0001"],
                closing_sequence=["q_clos0001"],
            )
        )
        result = validate_blueprint(blueprint)

        assert all(i.path for i in result.issues)

    def test_issue_includes_code(self):
        """Validation issues should include an error code."""
        blueprint = create_minimal_blueprint(
            question_flow=QuestionFlowSpec(
                opening_sequence=["q_invalid1"],
                core_sequence=["q_disc0001"],
                closing_sequence=["q_clos0001"],
            )
        )
        result = validate_blueprint(blueprint)

        assert all(i.code for i in result.issues)
