import pytest

from designdoc_mcp.document import generate_design_document
from designdoc_mcp.models import DebatePhase, Session, SessionStatus


class TestDocumentQuality:
    def test_empty_sections_show_placeholders(self):
        session = Session(
            session_id="test123",
            title="Test Session",
            description="A test session",
            status=SessionStatus.CREATED,
            current_phase=DebatePhase.CREATED,
        )
        doc = generate_design_document(session)

        assert "*No requirement has been submitted for this session.*" in doc
        assert "*No goals or constraints specified.*" in doc
        assert "*No assumptions were resolved during the clarification phase.*" in doc
        assert "*待辩论完成后生成。*" in doc
        assert "*No technical decisions recorded yet.*" in doc
        assert "*No acceptance criteria defined.*" in doc

    def test_all_required_sections_present(self):
        session = Session(
            session_id="test456",
            title="Test Session",
            description="A test session",
            status=SessionStatus.CREATED,
            current_phase=DebatePhase.CREATED,
        )
        doc = generate_design_document(session)

        required_sections = [
            "# Test Session",
            "## Overview",
            "## Requirement",
            "## Goals & Constraints",
            "## Assumption Decisions",
            "## Final Architecture",
            "## Technical Decisions",
            "## Data Model & API",
            "## Risks & Mitigations",
            "## Implementation Plan",
            "## Acceptance Criteria",
        ]
        for section in required_sections:
            assert section in doc, f"Missing section: {section}"
