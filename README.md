# Clara

AI-powered interview discovery platform for structured requirements gathering at scale.

## Overview

Clara enables organizations to conduct discovery interviews using AI agents configured by human managers. The platform dramatically reduces the cost and time required for requirements gathering, process discovery, and knowledge capture.

| Metric | Traditional Approach | Clara |
|--------|---------------------|-------|
| Cost per 20 interviews | $30,000 - $80,000 | $500 - $2,000 |
| Time to complete | 6-11 weeks | 3-5 days |
| Interview coverage | 5-10 stakeholders | 50-100+ participants |

## Key Features

- **Dynamic Interview Agents**: Configured via Interview Blueprint, not hardcoded
- **Knowledge Graph**: Neo4j stores entities with full evidence traceability
- **Real-time Adaptive UI**: AG-UI protocol enables dynamic interview components
- **Multi-Agent Synthesis**: A2A protocol coordinates analysis agents
- **Enterprise Integrations**: MCP connectors for Jira, Confluence

## Quick Start

```bash
# Clone and setup
git clone <repo>
cd ClaraMap

# Start infrastructure
docker-compose up -d

# Backend
cd src/backend
uv sync
uv run uvicorn clara.main:app --reload

# Frontend (new terminal)
cd src/frontend
pnpm install
pnpm dev
```

## Documentation

- [Design Documents](/Users/mantiz/Clara-Analysis/) - Architecture specs
- [API Documentation](docs/) - API reference
- [CLAUDE.md](CLAUDE.md) - Development guidance

## License

Proprietary
