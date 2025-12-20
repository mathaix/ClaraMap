# Clara Backend

AI-powered interview discovery platform backend.

## Development

```bash
# Install dependencies
uv sync --all-extras

# Run development server
uv run uvicorn clara.main:app --reload --port 8000

# Run tests
uv run pytest

# Type checking
uv run mypy clara

# Linting
uv run ruff check clara
```
