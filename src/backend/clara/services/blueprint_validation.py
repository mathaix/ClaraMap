"""Blueprint validation service with quality scoring.

Validates Interview Blueprints for:
- Cross-reference integrity (question IDs, entity references, goal references)
- Structural completeness
- Quality scoring with weighted dimensions

Quality Score Weights:
- Completeness: 25%
- Coherence: 20%
- Question Quality: 20%
- Extraction Coverage: 20%
- Persona Quality: 15%

Threshold: 70+ is considered ready for deployment.
"""

from dataclasses import dataclass, field
from enum import StrEnum

from clara.models.blueprint.agent import QuestionCategory
from clara.models.blueprint.core import InterviewBlueprint


class ValidationSeverity(StrEnum):
    """Severity level for validation issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """A single validation issue found in the blueprint."""

    severity: ValidationSeverity
    code: str
    message: str
    path: str
    agent_id: str | None = None


@dataclass
class QualityDimension:
    """Score for a single quality dimension."""

    name: str
    score: float
    weight: float
    issues: list[str] = field(default_factory=list)

    @property
    def weighted_score(self) -> float:
        """Calculate weighted contribution to total score."""
        return self.score * self.weight


@dataclass
class ValidationResult:
    """Complete validation result including issues and quality score."""

    is_valid: bool
    issues: list[ValidationIssue]
    quality_score: float
    quality_dimensions: list[QualityDimension]
    ready_for_deployment: bool

    @property
    def error_count(self) -> int:
        """Count of error-level issues."""
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        """Count of warning-level issues."""
        return sum(1 for i in self.issues if i.severity == ValidationSeverity.WARNING)


class BlueprintValidator:
    """Validates Interview Blueprints and calculates quality scores."""

    DEPLOYMENT_THRESHOLD = 70.0

    # Quality dimension weights (must sum to 1.0)
    WEIGHTS = {
        "completeness": 0.25,
        "coherence": 0.20,
        "question_quality": 0.20,
        "extraction_coverage": 0.20,
        "persona_quality": 0.15,
    }

    def validate(self, blueprint: InterviewBlueprint) -> ValidationResult:
        """Validate a blueprint and calculate quality score.

        Args:
            blueprint: The InterviewBlueprint to validate

        Returns:
            ValidationResult with issues and quality score
        """
        issues: list[ValidationIssue] = []

        # Run all validation checks
        issues.extend(self._validate_cross_references(blueprint))
        issues.extend(self._validate_entity_references(blueprint))
        issues.extend(self._validate_goal_references(blueprint))
        issues.extend(self._validate_synthesis_references(blueprint))

        # Calculate quality dimensions
        dimensions = self._calculate_quality_dimensions(blueprint, issues)

        # Calculate total quality score
        quality_score = sum(d.weighted_score for d in dimensions)

        # Blueprint is valid if no error-level issues
        is_valid = not any(i.severity == ValidationSeverity.ERROR for i in issues)

        return ValidationResult(
            is_valid=is_valid,
            issues=issues,
            quality_score=round(quality_score, 2),
            quality_dimensions=dimensions,
            ready_for_deployment=is_valid and quality_score >= self.DEPLOYMENT_THRESHOLD,
        )

    def _validate_cross_references(self, blueprint: InterviewBlueprint) -> list[ValidationIssue]:
        """Validate that question IDs in flows exist in questions list."""
        issues: list[ValidationIssue] = []

        for agent in blueprint.agents:
            question_ids = {q.id for q in agent.questions}

            # Check opening sequence
            for qid in agent.question_flow.opening_sequence:
                if qid not in question_ids:
                    issues.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            code="INVALID_QUESTION_REF",
                            message=f"Question '{qid}' in opening_sequence not found in questions",
                            path=f"agents[{agent.id}].question_flow.opening_sequence",
                            agent_id=agent.id,
                        )
                    )

            # Check core sequence
            for qid in agent.question_flow.core_sequence:
                if qid not in question_ids:
                    issues.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            code="INVALID_QUESTION_REF",
                            message=f"Question '{qid}' in core_sequence not found in questions",
                            path=f"agents[{agent.id}].question_flow.core_sequence",
                            agent_id=agent.id,
                        )
                    )

            # Check sensitive sequence
            for qid in agent.question_flow.sensitive_sequence:
                if qid not in question_ids:
                    issues.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            code="INVALID_QUESTION_REF",
                            message=f"Question '{qid}' in sensitive_sequence not found",
                            path=f"agents[{agent.id}].question_flow.sensitive_sequence",
                            agent_id=agent.id,
                        )
                    )

            # Check closing sequence
            for qid in agent.question_flow.closing_sequence:
                if qid not in question_ids:
                    issues.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            code="INVALID_QUESTION_REF",
                            message=f"Question '{qid}' in closing_sequence not found in questions",
                            path=f"agents[{agent.id}].question_flow.closing_sequence",
                            agent_id=agent.id,
                        )
                    )

        return issues

    def _validate_entity_references(self, blueprint: InterviewBlueprint) -> list[ValidationIssue]:
        """Validate that entity references in questions exist in extraction schema."""
        issues: list[ValidationIssue] = []

        for agent in blueprint.agents:
            entity_names = {e.name for e in agent.extraction.entities}

            for question in agent.questions:
                for entity_ref in question.expected_entities:
                    if entity_ref not in entity_names:
                        issues.append(
                            ValidationIssue(
                                severity=ValidationSeverity.WARNING,
                                code="INVALID_ENTITY_REF",
                                message=f"Entity '{entity_ref}' not in extraction schema",
                                path=f"agents[{agent.id}].questions[{question.id}].expected_entities",
                                agent_id=agent.id,
                            )
                        )

        return issues

    def _validate_goal_references(self, blueprint: InterviewBlueprint) -> list[ValidationIssue]:
        """Validate that goal references in questions exist in goals list."""
        issues: list[ValidationIssue] = []

        for agent in blueprint.agents:
            question_ids = {q.id for q in agent.questions}

            # Check goal -> question references
            for goal in agent.goals:
                for qid in goal.related_questions:
                    if qid not in question_ids:
                        issues.append(
                            ValidationIssue(
                                severity=ValidationSeverity.WARNING,
                                code="INVALID_QUESTION_REF_IN_GOAL",
                                message=f"Question '{qid}' in goal '{goal.id}' not found",
                                path=f"agents[{agent.id}].goals[{goal.id}].related_questions",
                                agent_id=agent.id,
                            )
                        )

        return issues

    def _validate_synthesis_references(
        self, blueprint: InterviewBlueprint
    ) -> list[ValidationIssue]:
        """Validate that entity types in synthesis rules exist."""
        issues: list[ValidationIssue] = []

        all_entity_types = blueprint.get_all_entity_types()

        # Check entity resolution rules
        for rule in blueprint.synthesis.entity_resolution_rules:
            if rule.entity_type not in all_entity_types:
                issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        code="INVALID_ENTITY_TYPE_IN_SYNTHESIS",
                        message=f"Entity type '{rule.entity_type}' not found in agents",
                        path=f"synthesis.entity_resolution_rules[{rule.entity_type}]",
                        agent_id=None,
                    )
                )

        # Check correlation rules
        for rule in blueprint.synthesis.correlation_rules:
            for entity_type in rule.entities_involved:
                if entity_type not in all_entity_types:
                    issues.append(
                        ValidationIssue(
                            severity=ValidationSeverity.WARNING,
                            code="INVALID_ENTITY_TYPE_IN_CORRELATION",
                            message=f"Entity type '{entity_type}' not found in agents",
                            path=f"synthesis.correlation_rules[{rule.name}].entities_involved",
                            agent_id=None,
                        )
                    )

        return issues

    def _calculate_quality_dimensions(
        self, blueprint: InterviewBlueprint, issues: list[ValidationIssue]
    ) -> list[QualityDimension]:
        """Calculate quality scores for each dimension."""
        dimensions: list[QualityDimension] = []

        # Calculate each dimension
        dimensions.append(self._score_completeness(blueprint))
        dimensions.append(self._score_coherence(blueprint, issues))
        dimensions.append(self._score_question_quality(blueprint))
        dimensions.append(self._score_extraction_coverage(blueprint))
        dimensions.append(self._score_persona_quality(blueprint))

        return dimensions

    def _score_completeness(self, blueprint: InterviewBlueprint) -> QualityDimension:
        """Score blueprint completeness (0-100).

        Checks for:
        - Project context fully specified
        - All agents have required fields
        - Synthesis rules defined
        - Quality thresholds set
        """
        score = 100.0
        issues: list[str] = []

        # Check project context
        if not blueprint.project.business_context:
            score -= 10
            issues.append("Missing business context")
        if not blueprint.project.decision_to_inform:
            score -= 10
            issues.append("Missing decision_to_inform")
        if not blueprint.project.stakeholders:
            score -= 5
            issues.append("No stakeholders defined")

        # Check agents
        for agent in blueprint.agents:
            if not agent.design_rationale:
                score -= 5
                issues.append(f"Agent '{agent.id}' missing design rationale")
            if not agent.target_interviewees.selection_criteria:
                score -= 3
                issues.append(f"Agent '{agent.id}' missing selection criteria")

        # Check synthesis
        if not blueprint.synthesis.entity_resolution_rules:
            score -= 10
            issues.append("No entity resolution rules defined")
        if not blueprint.synthesis.correlation_rules:
            score -= 5
            issues.append("No correlation rules defined")

        # Check quality spec
        if not blueprint.quality.test_scenarios:
            score -= 10
            issues.append("No test scenarios defined")

        return QualityDimension(
            name="completeness",
            score=max(0, score),
            weight=self.WEIGHTS["completeness"],
            issues=issues,
        )

    def _score_coherence(
        self, blueprint: InterviewBlueprint, validation_issues: list[ValidationIssue]
    ) -> QualityDimension:
        """Score blueprint coherence (0-100).

        Based on:
        - Cross-reference validity
        - Goal-question alignment
        - Flow sequence coverage
        """
        score = 100.0
        issues: list[str] = []

        # Deduct for validation errors
        error_count = sum(1 for i in validation_issues if i.severity == ValidationSeverity.ERROR)
        warning_count = sum(
            1 for i in validation_issues if i.severity == ValidationSeverity.WARNING
        )

        score -= error_count * 15  # Errors are severe
        score -= warning_count * 5  # Warnings are less severe

        if error_count > 0:
            issues.append(f"{error_count} cross-reference errors")
        if warning_count > 0:
            issues.append(f"{warning_count} reference warnings")

        # Check question flow coverage
        for agent in blueprint.agents:
            flow = agent.question_flow
            all_flow_questions = set(
                flow.opening_sequence
                + flow.core_sequence
                + flow.sensitive_sequence
                + flow.closing_sequence
            )
            all_questions = {q.id for q in agent.questions}

            unused = all_questions - all_flow_questions
            if unused:
                score -= len(unused) * 3
                issues.append(f"Agent '{agent.id}': {len(unused)} questions not in any flow")

        return QualityDimension(
            name="coherence",
            score=max(0, score),
            weight=self.WEIGHTS["coherence"],
            issues=issues,
        )

    def _score_question_quality(self, blueprint: InterviewBlueprint) -> QualityDimension:
        """Score question quality (0-100).

        Based on:
        - Question diversity (categories used)
        - Probing guidance provided
        - Follow-up questions defined
        - Skip conditions for adaptive flow
        """
        score = 100.0
        issues: list[str] = []

        for agent in blueprint.agents:
            questions = agent.questions

            # Check category diversity
            categories_used = {q.category for q in questions}
            expected_categories = {
                QuestionCategory.RAPPORT,
                QuestionCategory.DISCOVERY,
                QuestionCategory.CLOSING,
            }
            missing = expected_categories - categories_used
            if missing:
                score -= len(missing) * 5
                issues.append(f"Agent '{agent.id}': Missing question categories: {missing}")

            # Check for probing guidance
            questions_with_probing = sum(1 for q in questions if q.probing_triggers)
            probing_ratio = questions_with_probing / len(questions) if questions else 0
            if probing_ratio < 0.3:
                score -= 10
                issues.append(f"Agent '{agent.id}': Low probing coverage ({probing_ratio:.0%})")

            # Check for follow-ups
            questions_with_followups = sum(1 for q in questions if q.follow_up_questions)
            followup_ratio = questions_with_followups / len(questions) if questions else 0
            if followup_ratio < 0.4:
                score -= 10
                issues.append(f"Agent '{agent.id}': Low follow-up coverage ({followup_ratio:.0%})")

            # Check for adaptive skip conditions
            questions_with_skips = sum(1 for q in questions if q.skip_conditions)
            if questions_with_skips < 2:
                score -= 5
                issues.append(f"Agent '{agent.id}': Few skip conditions for adaptive flow")

        return QualityDimension(
            name="question_quality",
            score=max(0, score),
            weight=self.WEIGHTS["question_quality"],
            issues=issues,
        )

    def _score_extraction_coverage(self, blueprint: InterviewBlueprint) -> QualityDimension:
        """Score extraction schema coverage (0-100).

        Based on:
        - Entity definitions completeness
        - Relationship definitions
        - Question-to-entity mapping
        - Sentiment tracking
        """
        score = 100.0
        issues: list[str] = []

        for agent in blueprint.agents:
            extraction = agent.extraction

            # Check entity field completeness
            for entity in extraction.entities:
                required_fields = sum(1 for f in entity.fields if f.required)
                if required_fields == 0:
                    score -= 5
                    issues.append(f"Entity '{entity.name}': No required fields defined")
                if not entity.examples:
                    score -= 3
                    issues.append(f"Entity '{entity.name}': No examples provided")

            # Check relationship coverage
            if len(extraction.entities) > 1 and not extraction.relationships:
                score -= 15
                issues.append(f"Agent '{agent.id}': Multiple entities but no relationships")

            # Check question-to-entity mapping
            questions_with_entities = sum(1 for q in agent.questions if q.expected_entities)
            entity_mapping_ratio = (
                questions_with_entities / len(agent.questions) if agent.questions else 0
            )
            if entity_mapping_ratio < 0.5:
                score -= 10
                issues.append(
                    f"Agent '{agent.id}': Low entity mapping ({entity_mapping_ratio:.0%})"
                )

            # Check sentiment tracking
            if not extraction.sentiments:
                score -= 5
                issues.append(f"Agent '{agent.id}': No sentiment tracking defined")

        return QualityDimension(
            name="extraction_coverage",
            score=max(0, score),
            weight=self.WEIGHTS["extraction_coverage"],
            issues=issues,
        )

    def _score_persona_quality(self, blueprint: InterviewBlueprint) -> QualityDimension:
        """Score persona definition quality (0-100).

        Based on:
        - Persona completeness
        - Expertise alignment with project
        - Handling strategies defined
        """
        score = 100.0
        issues: list[str] = []

        for agent in blueprint.agents:
            persona = agent.persona

            # Check expertise diversity
            if len(persona.expertise) < 2:
                score -= 10
                issues.append(f"Agent '{agent.id}': Limited expertise areas")

            # Check handling strategies
            if len(persona.handling_reluctance) < 20:
                score -= 10
                issues.append(f"Agent '{agent.id}': Brief reluctance handling strategy")

            # Check rapport approach
            if len(persona.rapport_building_approach) < 20:
                score -= 10
                issues.append(f"Agent '{agent.id}': Brief rapport approach")

            # Check communication style detail
            if len(persona.communication_style) < 20:
                score -= 5
                issues.append(f"Agent '{agent.id}': Brief communication style")

        return QualityDimension(
            name="persona_quality",
            score=max(0, score),
            weight=self.WEIGHTS["persona_quality"],
            issues=issues,
        )


# Singleton instance for convenience
validator = BlueprintValidator()


def validate_blueprint(blueprint: InterviewBlueprint) -> ValidationResult:
    """Convenience function to validate a blueprint."""
    return validator.validate(blueprint)
