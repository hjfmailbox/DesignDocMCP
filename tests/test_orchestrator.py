from __future__ import annotations

import asyncio
import json
import pytest
from unittest.mock import MagicMock, AsyncMock

pytestmark = pytest.mark.anyio

from designdoc_mcp.orchestrator import (
    AgentConfig,
    AgentExecutor,
    Orchestrator,
    PromptBuilder,
    ResultParser,
)
from designdoc_mcp.models import (
    AgentInfo,
    DebatePhase,
    Session,
    SessionStatus,
    VoteType,
)


class TestPromptBuilder:
    def test_build_proposal_prompt(self):
        session = MagicMock()
        session.session_id = "sess_123"
        session.current_round = 1
        session.requirement = None

        agent = MagicMock()
        agent.agent_id = "agent_a"
        agent.name = "Alice"
        agent.current_perspective = "scalability"

        context = {"perspective_description": "Focus on growth"}
        prompt = PromptBuilder.build(session, agent, DebatePhase.PROPOSAL, context)

        assert "sess_123" in prompt
        assert "proposal" in prompt
        assert "scalability" in prompt
        assert "JSON" in prompt


class TestResultParser:
    def test_extract_json_plain(self):
        data = ResultParser.extract_json('{"architecture": "microservices"}')
        assert data["architecture"] == "microservices"

    def test_extract_json_with_fences(self):
        raw = '```json\n{"vote_type": "agree"}\n```'
        data = ResultParser.extract_json(raw)
        assert data["vote_type"] == "agree"

    def test_parse_proposal(self):
        data = {"architecture": "a", "tech_stack": "b"}
        result = ResultParser.parse_proposal(data)
        assert result["architecture"] == "a"
        assert "raw_content" in result

    def test_parse_challenge_auto_correct_self_target(self):
        session = MagicMock()
        session.current_round = 1
        p1 = MagicMock()
        p1.agent_id = "agent_a"
        p1.proposal_id = "prop_1"
        p1.round_number = 1
        p2 = MagicMock()
        p2.agent_id = "agent_b"
        p2.proposal_id = "prop_2"
        p2.round_number = 1
        session.proposals = [p1, p2]
        session.agents = [MagicMock(is_active=True), MagicMock(is_active=True)]

        data = {"target_agent_id": "agent_a", "target_proposal_id": "prop_1", "risks": []}
        result = ResultParser.parse_challenge(data, session, "agent_a")
        # Should auto-correct to agent_b since multi-agent mode forbids self-challenge
        assert result["target_agent_id"] == "agent_b"
        assert result["target_proposal_id"] == "prop_2"

    def test_parse_consensus_invalid_vote_defaults_to_abstain(self):
        data = {"vote_type": "invalid"}
        result = ResultParser.parse_consensus(data)
        assert result["vote_type"] == VoteType.ABSTAIN


class TestAgentExecutor:
    @pytest.mark.anyio
    async def test_execute_success(self):
        config = AgentConfig(
            agent_id="test",
            name="Test",
            command_template="echo '{prompt}'",
        )
        executor = AgentExecutor(config)
        stdout = await executor.execute("hello")
        assert "hello" in stdout

    @pytest.mark.asyncio
    async def test_execute_missing_placeholder_raises(self):
        config = AgentConfig(
            agent_id="test",
            name="Test",
            command_template="echo hello",
        )
        executor = AgentExecutor(config)
        with pytest.raises(ValueError):
            await executor.execute("hello")


class TestOrchestratorPendingAgents:
    def test_pending_proposal(self):
        engine = MagicMock()
        session = MagicMock()
        session.status = SessionStatus.PROPOSAL
        session.current_phase = DebatePhase.PROPOSAL
        session.current_round = 1
        session.agents = [
            MagicMock(agent_id="a", is_active=True),
            MagicMock(agent_id="b", is_active=True),
        ]
        session.proposals = [MagicMock(agent_id="a", round_number=1)]
        session.challenges = []
        session.revisions = []
        session.optimizations = []
        session.devils_advocates = []
        session.consensus_votes = []
        session.assumptions = []
        session.clarify_refine_submitted = []
        session.refined_requirements = []

        orch = Orchestrator(engine, [])
        pending = orch._pending_agents(session, ["a", "b"])
        assert pending == ["b"]

    def test_pending_devils_advocate(self):
        engine = MagicMock()
        session = MagicMock()
        session.status = SessionStatus.DEVILS_ADVOCATE
        session.current_phase = DebatePhase.DEVILS_ADVOCATE
        session.current_round = 1
        session.devils_advocate_agent = "da"
        session.devils_advocates = []

        orch = Orchestrator(engine, [])
        agents = orch._agents_for_phase(session)
        assert agents == ["da"]


class TestOrchestratorIntegration:
    @pytest.mark.asyncio
    async def test_run_session_completes_immediately(self):
        """If session is already COMPLETED, run_session exits immediately."""
        engine = MagicMock()
        store = MagicMock()
        session = MagicMock()
        session.status = SessionStatus.COMPLETED
        store.get_session.return_value = session
        engine.store = store

        orch = Orchestrator(engine, [])
        await orch.run_session("sess_1")
        # Should return without spawning anything

    @pytest.mark.asyncio
    async def test_run_session_human_review_breaks(self):
        """If session enters HUMAN_REVIEW, run_session breaks."""
        engine = MagicMock()
        store = MagicMock()
        session = MagicMock()
        session.status = SessionStatus.HUMAN_REVIEW
        store.get_session.return_value = session
        engine.store = store

        orch = Orchestrator(engine, [])
        await orch.run_session("sess_1")
