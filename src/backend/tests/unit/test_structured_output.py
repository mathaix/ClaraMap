"""Unit tests for structured output models used with Instructor."""

import pytest
from pydantic import ValidationError

from clara.agents.structured_output import (
    DataTableColumn,
    DataTableUIComponent,
    DesignAssistantResponse,
    NoUIComponent,
    ProcessMapUIComponent,
    RouterDecisionModel,
    SelectionListParams,
    SelectionOption,
    SelectionUIComponent,
)


class TestSelectionOption:
    """Tests for SelectionOption model."""

    def test_basic_option(self):
        option = SelectionOption(id="test", label="Test Option")
        assert option.id == "test"
        assert option.label == "Test Option"
        assert option.description is None
        assert option.requires_input is False

    def test_option_with_all_fields(self):
        option = SelectionOption(
            id="other",
            label="Other",
            description="Something else",
            requires_input=True,
        )
        assert option.requires_input is True
        assert option.description == "Something else"


class TestSelectionUIComponent:
    """Tests for SelectionUIComponent model."""

    def test_basic_selection(self):
        component = SelectionUIComponent(
            question="Choose an option",
            options=[
                SelectionOption(id="a", label="Option A"),
                SelectionOption(id="b", label="Option B"),
            ],
        )
        assert component.type == "selection"
        assert component.question == "Choose an option"
        assert len(component.options) == 3
        assert component.options[-1].label == "Other"
        assert component.options[-1].requires_input is True
        assert component.multi_select is False

    def test_multi_select(self):
        component = SelectionUIComponent(
            question="Select all that apply",
            options=[
                SelectionOption(id="a", label="Option A"),
                SelectionOption(id="b", label="Option B"),
            ],
            multi_select=True,
        )
        assert component.multi_select is True

    def test_too_few_options_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            SelectionUIComponent(
                question="Choose",
                options=[SelectionOption(id="a", label="Option A")],
            )
        assert "at least 2 options" in str(exc_info.value)

    def test_too_many_options_trims(self):
        options = [
            SelectionOption(id=f"opt{i}", label=f"Option {i}")
            for i in range(8)
        ]
        component = SelectionUIComponent(question="Choose", options=options)
        assert len(component.options) == 7
        assert component.options[-1].label == "Other"


class TestDataTableColumn:
    """Tests for DataTableColumn model."""

    def test_basic_column(self):
        column = DataTableColumn(name="Name")
        assert column.name == "Name"
        assert column.type == "text"
        assert column.required is False

    def test_enum_column(self):
        column = DataTableColumn(
            name="Priority",
            type="enum",
            required=True,
            options=["Low", "Medium", "High"],
        )
        assert column.type == "enum"
        assert column.options == ["Low", "Medium", "High"]


class TestDataTableUIComponent:
    """Tests for DataTableUIComponent model."""

    def test_basic_table(self):
        component = DataTableUIComponent(
            title="Stakeholder List",
            columns=[
                DataTableColumn(name="Name", required=True),
                DataTableColumn(name="Role"),
            ],
        )
        assert component.type == "data_table"
        assert component.title == "Stakeholder List"
        assert len(component.columns) == 2
        assert component.min_rows == 3
        assert component.starter_rows == 3


class TestProcessMapUIComponent:
    """Tests for ProcessMapUIComponent model."""

    def test_basic_process_map(self):
        component = ProcessMapUIComponent(title="Approval Workflow")
        assert component.type == "process_map"
        assert component.title == "Approval Workflow"
        assert "step_name" in component.required_fields
        assert "sequence" in component.edge_types
        assert component.min_steps == 3


class TestRouterDecisionModel:
    """Tests for RouterDecisionModel used by Instructor."""

    def test_chat_decision(self):
        decision = RouterDecisionModel(
            action="chat",
            confidence=0.8,
            rationale="Normal conversation",
        )
        assert decision.action == "chat"
        assert decision.tool_name is None
        assert decision.confidence == 0.8

    def test_tool_decision(self):
        decision = RouterDecisionModel(
            action="tool",
            tool_name="request_data_table",
            confidence=0.9,
            rationale="User wants to list stakeholders",
        )
        assert decision.action == "tool"
        assert decision.tool_name == "request_data_table"

    def test_tool_decision_requires_tool_name(self):
        with pytest.raises(ValidationError) as exc_info:
            RouterDecisionModel(
                action="tool",
                confidence=0.8,
                rationale="Missing tool name",
            )
        assert "tool_name is required" in str(exc_info.value)

    def test_clarify_decision(self):
        decision = RouterDecisionModel(
            action="clarify",
            confidence=0.5,
            rationale="Need more info",
            clarifying_question="How many items?",
        )
        assert decision.action == "clarify"
        assert decision.clarifying_question == "How many items?"

    def test_clarify_requires_question(self):
        with pytest.raises(ValidationError) as exc_info:
            RouterDecisionModel(
                action="clarify",
                confidence=0.5,
                rationale="Need clarification",
            )
        assert "clarifying_question is required" in str(exc_info.value)

    def test_confidence_bounds(self):
        with pytest.raises(ValidationError):
            RouterDecisionModel(
                action="chat",
                confidence=1.5,
                rationale="Too confident",
            )

        with pytest.raises(ValidationError):
            RouterDecisionModel(
                action="chat",
                confidence=-0.1,
                rationale="Negative confidence",
            )


class TestDesignAssistantResponse:
    """Tests for DesignAssistantResponse model."""

    def test_chat_only_response(self):
        response = DesignAssistantResponse(
            display_text="Hello! How can I help you today?",
        )
        assert response.display_text == "Hello! How can I help you today?"
        assert isinstance(response.ui_component, NoUIComponent)
        assert response.phase_transition is None

    def test_response_with_selection(self):
        response = DesignAssistantResponse(
            display_text="What type of project?",
            ui_component=SelectionUIComponent(
                question="Select project type",
                options=[
                    SelectionOption(id="ma", label="M&A"),
                    SelectionOption(id="migration", label="Migration"),
                ],
            ),
        )
        assert isinstance(response.ui_component, SelectionUIComponent)
        assert response.ui_component.question == "Select project type"

    def test_response_with_phase_transition(self):
        response = DesignAssistantResponse(
            display_text="Let's move on to configuration.",
            phase_transition="agent_configuration",
        )
        assert response.phase_transition == "agent_configuration"

    def test_empty_display_text_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            DesignAssistantResponse(display_text="")
        assert "display_text cannot be empty" in str(exc_info.value)

    def test_whitespace_only_display_text_raises(self):
        with pytest.raises(ValidationError) as exc_info:
            DesignAssistantResponse(display_text="   \n\t  ")
        assert "display_text cannot be empty" in str(exc_info.value)


class TestSelectionListParams:
    """Tests for SelectionListParams model."""

    def test_auto_adds_other_option(self):
        params = SelectionListParams(
            question="Choose a project type",
            options=[
                SelectionOption(id="ma", label="M&A"),
                SelectionOption(id="migration", label="Migration"),
            ],
        )
        # Should auto-add "Other" option
        assert len(params.options) == 3
        other_option = params.options[-1]
        assert other_option.id == "other"
        assert other_option.label == "Other"
        assert other_option.requires_input is True

    def test_does_not_duplicate_other(self):
        params = SelectionListParams(
            question="Choose",
            options=[
                SelectionOption(id="a", label="Option A"),
                SelectionOption(id="other", label="Other", requires_input=True),
            ],
        )
        # Should not add another "Other"
        assert len(params.options) == 2

    def test_too_few_options_raises(self):
        with pytest.raises(ValidationError):
            SelectionListParams(
                question="Choose",
                options=[SelectionOption(id="a", label="Option A")],
            )
