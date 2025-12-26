"""Clara testing utilities for LLM compliance testing.

Usage:
    # Run flow test from command line
    uv run python -m clara.testing.flow_runner personas_step

    # Import programmatically
    from clara.testing.flow_runner import FlowRunner
"""

__all__ = ["FlowRunner", "FlowSpec", "StepResult"]


def __getattr__(name: str):
    """Lazy import to avoid circular import warning when running as module."""
    if name in __all__:
        from . import flow_runner

        return getattr(flow_runner, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
