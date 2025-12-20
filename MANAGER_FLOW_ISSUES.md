# Manager Flow & Blueprint - GitHub Issues Summary

This document organizes all GitHub issues created for the Manager Flow and Interview Blueprint features.

## Overview

**Total Issues Created**: 41 (7 Epics + 34 Stories)

All issues are available at: https://github.com/mathaix/ClaraMap/issues

---

## Epic 1: Project Management
**Issue**: [#2](https://github.com/mathaix/ClaraMap/issues/2)

Enable managers to create and manage discovery projects.

### Stories
- [#3](https://github.com/mathaix/ClaraMap/issues/3) - Create Discovery Project (PM-01) **[MUST]**
- [#4](https://github.com/mathaix/ClaraMap/issues/4) - Project Dashboard & List View (PM-02) **[MUST]**
- [#5](https://github.com/mathaix/ClaraMap/issues/5) - Project Type Selection (PM-05) **[MUST]**
- [#6](https://github.com/mathaix/ClaraMap/issues/6) - Archive and Delete Projects (PM-03) **[SHOULD]**
- [#7](https://github.com/mathaix/ClaraMap/issues/7) - Duplicate Project as Template (PM-04) **[COULD]**

---

## Epic 2: Design Assistant (Opus-Powered)
**Issue**: [#8](https://github.com/mathaix/ClaraMap/issues/8)

Conversational AI that helps managers design Interview Blueprints through guided dialogue.

### Stories
- [#9](https://github.com/mathaix/ClaraMap/issues/9) - Design Assistant Conversation Interface (AG-01, AG-02) **[MUST]**
- [#10](https://github.com/mathaix/ClaraMap/issues/10) - Discovery Phase & Clarifying Questions **[MUST]**
- [#11](https://github.com/mathaix/ClaraMap/issues/11) - MCP Context Gathering (AG-03) **[SHOULD]**
- [#12](https://github.com/mathaix/ClaraMap/issues/12) - Blueprint Drafting with Reasoning **[MUST]**
- [#13](https://github.com/mathaix/ClaraMap/issues/13) - Blueprint Refinement & Iteration **[MUST]**
- [#14](https://github.com/mathaix/ClaraMap/issues/14) - Quality Checks & Validation **[MUST]**
- [#15](https://github.com/mathaix/ClaraMap/issues/15) - Test Scenario Generation **[SHOULD]**
- [#16](https://github.com/mathaix/ClaraMap/issues/16) - Session State Management **[MUST]**

---

## Epic 3: Interview Blueprint Schema & Storage
**Issue**: [#17](https://github.com/mathaix/ClaraMap/issues/17)

The single source of truth that drives all Clara functionality.

### Stories
- [#18](https://github.com/mathaix/ClaraMap/issues/18) - Blueprint Core Schema Definition **[MUST]**
- [#19](https://github.com/mathaix/ClaraMap/issues/19) - Agent Blueprint Schema **[MUST]**
- [#20](https://github.com/mathaix/ClaraMap/issues/20) - Extraction Schema Definition **[MUST]**
- [#21](https://github.com/mathaix/ClaraMap/issues/21) - Synthesis Rules Schema **[MUST]**
- [#22](https://github.com/mathaix/ClaraMap/issues/22) - Blueprint Storage & Versioning (AG-08) **[MUST]**
- [#23](https://github.com/mathaix/ClaraMap/issues/23) - Blueprint Validation Service **[MUST]**
- [#24](https://github.com/mathaix/ClaraMap/issues/24) - Agent Factory: Blueprint to Agent (AG-04, AG-05) **[MUST]**

---

## Epic 4: Interview Invitations & Participant Management
**Issue**: [#25](https://github.com/mathaix/ClaraMap/issues/25)

Enable managers to invite interviewees and manage the invitation lifecycle.

### Stories
- [#26](https://github.com/mathaix/ClaraMap/issues/26) - Send Interview Invitations (IN-01, IN-06) **[MUST]**
- [#27](https://github.com/mathaix/ClaraMap/issues/27) - Assign Interviewee to Agent (IN-02, IN-03) **[MUST]**
- [#28](https://github.com/mathaix/ClaraMap/issues/28) - Manage Invitation Lifecycle (IN-05, IN-07) **[SHOULD]**
- [#29](https://github.com/mathaix/ClaraMap/issues/29) - Bulk Import Invitees via CSV (IN-08) **[COULD]**

---

## Epic 5: Live Interview Monitoring
**Issue**: [#30](https://github.com/mathaix/ClaraMap/issues/30)

Real-time visibility into active interviews with intervention capabilities.

### Stories
- [#31](https://github.com/mathaix/ClaraMap/issues/31) - Active Interview Dashboard (LM-01, LM-07) **[MUST]**
- [#32](https://github.com/mathaix/ClaraMap/issues/32) - Real-time Transcript Viewer (LM-02) **[MUST]**
- [#33](https://github.com/mathaix/ClaraMap/issues/33) - Live Entity Extraction Feed (LM-03) **[SHOULD]**
- [#34](https://github.com/mathaix/ClaraMap/issues/34) - Manager Intervention Controls (LM-04, LM-05, LM-06) **[SHOULD]**
- [#35](https://github.com/mathaix/ClaraMap/issues/35) - Interview Progress & Coverage Metrics (LM-07) **[SHOULD]**

---

## Epic 6: Results, Synthesis & Export
**Issue**: [#36](https://github.com/mathaix/ClaraMap/issues/36)

View results, explore knowledge graph, and export deliverables.

### Stories
- [#37](https://github.com/mathaix/ClaraMap/issues/37) - View Interview Transcripts & Summaries (RS-01, RS-02, RS-03) **[MUST]**
- [#38](https://github.com/mathaix/ClaraMap/issues/38) - Knowledge Graph Visualization (RS-04) **[SHOULD]**
- [#39](https://github.com/mathaix/ClaraMap/issues/39) - Synthesis Report Generation (RS-06, RS-09) **[MUST]**
- [#40](https://github.com/mathaix/ClaraMap/issues/40) - Multi-Format Export (RS-07) **[MUST]**
- [#41](https://github.com/mathaix/ClaraMap/issues/41) - Interview Metrics & Analytics (RS-08) **[SHOULD]**
- [#42](https://github.com/mathaix/ClaraMap/issues/42) - Evidence Traceability UI (RS-09) **[MUST]**

---

## Priority Breakdown

### Must Have (Critical Path)
20 stories marked as **[MUST]** - these are essential for MVP.

Key must-haves:
- Project creation and dashboard
- Design Assistant conversation and blueprint generation
- Blueprint schema and validation
- Interview invitations and agent assignment
- Live interview monitoring
- Synthesis report generation with evidence
- Multi-format export

### Should Have (High Value)
11 stories marked as **[SHOULD]** - important for complete experience.

Includes:
- MCP context gathering
- Invitation lifecycle management
- Entity extraction feed
- Manager intervention
- Knowledge graph visualization
- Metrics and analytics

### Could Have (Nice to Have)
3 stories marked as **[COULD]** - enhance usability.

Includes:
- Duplicate project as template
- Bulk CSV import

---

## Implementation Sequence (Recommended)

### Phase 1: Foundation (Weeks 1-3)
1. **Epic 1**: Project Management (#2-7)
2. **Epic 3**: Blueprint Schema (#17-24)
   - Start with core schema (#18-21)
   - Then storage/validation (#22-23)
   - Finally agent factory (#24)

### Phase 2: Blueprint Creation (Weeks 4-6)
3. **Epic 2**: Design Assistant (#8-16)
   - Conversation interface first (#9)
   - Discovery and drafting (#10, #12)
   - Refinement and quality (#13, #14)
   - State management (#16)
   - MCP integration can come later (#11)

### Phase 3: Interview Execution (Weeks 7-8)
4. **Epic 4**: Invitations (#25-29)
   - Core invitation flow (#26-27)
   - Lifecycle management (#28)
   - Bulk import optional (#29)

### Phase 4: Monitoring & Results (Weeks 9-11)
5. **Epic 5**: Live Monitoring (#30-35)
   - Dashboard and transcript viewer (#31-32)
   - Entity feed and intervention (#33-34)
6. **Epic 6**: Results & Export (#36-42)
   - Transcripts first (#37)
   - Synthesis pipeline (#39)
   - Export formats (#40)
   - Evidence traceability (#42)
   - Graph viz and metrics optional (#38, #41)

---

## Key Dependencies

### Technical Dependencies
- **Database**: PostgreSQL for projects, blueprints, interviews
- **Graph Database**: Neo4j for entities and evidence chain
- **Real-time**: AG-UI protocol (SSE) for streaming
- **LLM**: Claude via Pydantic AI
- **MCP**: Jira, Confluence integrations
- **Storage**: S3 for files and exports

### Cross-Epic Dependencies
- Blueprint Schema (#17) → Design Assistant (#8) → Agent Factory (#24)
- Agent Factory (#24) → Invitations (#25) → Live Monitoring (#30)
- Live Monitoring (#30) → Results & Export (#36)

---

## Success Metrics

### Manager Experience
- Complete agent design in < 30 minutes
- Create project in < 2 minutes
- Dashboard loads in < 3 seconds
- Manager NPS > 50

### System Performance
- Agent responses streaming within 2 seconds
- Entity extraction visible within 2 seconds
- Synthesis report generated within 5 minutes
- Export generation < 30 seconds

### Quality
- Evidence traceability: 100% of claims linked to quotes
- Interview completion rate > 85%
- Extraction F1 score > 0.85
- Quality check score ≥ 70

---

## Notes

- All issues include detailed acceptance criteria
- Requirement IDs (PM-01, AG-01, etc.) reference PRD
- MoSCoW prioritization applied
- Each story is independently testable
- Full technical implementation notes included

---

**Generated**: 2025-12-19
**Repository**: https://github.com/mathaix/ClaraMap
