"""DesignDoc MCP 单元测试与集成测试"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from designdoc_mcp.clarity_config import (
    DIMENSION_KEYWORDS,
    FIELD_COMPLETION_BONUS,
    LENGTH_NORMALIZATION_FACTOR,
    MAX_CLARITY_SCORE,
    MAX_LENGTH_BONUS,
    validate_config,
)
from designdoc_mcp.document import generate_design_document
from designdoc_mcp.engine import CollaborationEngine
from designdoc_mcp.models import (
    ChallengePriority,
    DebatePhase,
    Session,
    SessionStatus,
    VoteType,
)
from designdoc_mcp.store import SessionStore


@pytest.fixture
def tmp_store(tmp_path):
    return SessionStore(data_dir=str(tmp_path))


@pytest.fixture
def engine(tmp_store):
    return CollaborationEngine(tmp_store)


@pytest.fixture
def session_with_agents(engine):
    """创建 session 并注册两个 agent（不带 model，agent_id = name.lower()）"""
    session = engine.create_session(title="Test Session", description="A test session")
    a1 = engine.register_agent(session_id=session.session_id, name="AgentA")
    a2 = engine.register_agent(session_id=session.session_id, name="AgentB")
    # agent_id = name.lower().replace(" ", "_") = "agenta" / "agentb"
    return session


# ==================== clarity_config 测试 ====================


class TestClarityConfig:
    def test_dimension_keywords_match_clarity_dimensions(self):
        from designdoc_mcp.models import CLARITY_DIMENSIONS
        assert set(DIMENSION_KEYWORDS.keys()) == set(CLARITY_DIMENSIONS)

    def test_no_empty_keyword_lists(self):
        for dim, keywords in DIMENSION_KEYWORDS.items():
            assert len(keywords) > 0, f"Dimension '{dim}' has empty keyword list"

    def test_validate_config_passes(self):
        assert validate_config() is True

    def test_scoring_constants_in_valid_range(self):
        assert 0 <= MAX_LENGTH_BONUS <= 1
        assert LENGTH_NORMALIZATION_FACTOR > 0
        assert 0 <= FIELD_COMPLETION_BONUS <= 1
        assert 0 < MAX_CLARITY_SCORE <= 1


# ==================== 版本号一致性测试 ====================


class TestVersionConsistency:
    def test_pyproject_version_matches_server(self):
        from designdoc_mcp.server import mcp
        pyproject_path = Path(__file__).resolve().parent.parent / "pyproject.toml"
        content = pyproject_path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.startswith("version ="):
                pyproject_version = line.split('"')[1]
                break
        assert pyproject_version == mcp.version


# ==================== Store 测试 ====================


class TestSessionStore:
    def test_save_updates_mtime_cache(self, tmp_store):
        session = Session(session_id="test1", title="T", description="D")
        tmp_store.create_session(session)
        assert "test1" in tmp_store._mtimes
        mtime1 = tmp_store._mtimes["test1"]

        # 修改并保存
        session.title = "Updated"
        tmp_store.update_session(session)
        mtime2 = tmp_store._mtimes["test1"]
        assert mtime2 >= mtime1

    def test_get_session_uses_mtime_cache(self, tmp_store):
        session = Session(session_id="test2", title="T", description="D")
        tmp_store.create_session(session)

        # 第二次获取应使用缓存，不重新读取
        result = tmp_store.get_session("test2")
        assert result is not None
        assert result.title == "T"


# ==================== Engine 测试 ====================


class TestSubmitAssumptionsMultiRound:
    def test_assumption_has_clarify_round(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)

        assumptions = engine.submit_assumptions(
            sid, "agenta", [{"dimension": "core_entities", "assumption": "Test assumption"}]
        )
        assert assumptions[0].clarify_round == 1

    def test_same_agent_cannot_submit_twice_same_round(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)

        engine.submit_assumptions(
            sid, "agenta", [{"dimension": "core_entities", "assumption": "Assumption 1"}]
        )
        with pytest.raises(ValueError, match="already submitted"):
            engine.submit_assumptions(
                sid, "agenta", [{"dimension": "data_storage", "assumption": "Assumption 2"}]
            )


class TestSubmitChallengeValidation:
    def test_cannot_challenge_own_proposal(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)

        # 提交提案
        engine.submit_proposal(sid, "agenta", architecture="Arch A")
        engine.submit_proposal(sid, "agentb", architecture="Arch B")

        # 获取 proposal id
        session = engine.store.get_session(sid)
        proposal_a = [p for p in session.proposals if p.agent_id == "agenta"][0]

        with pytest.raises(ValueError, match="Cannot challenge your own"):
            engine.submit_challenge(
                sid, "agenta", "agenta", proposal_a.proposal_id,
                risks=["Risk 1"], missing_considerations=["Missing 1"],
            )

    def test_cannot_challenge_nonexistent_proposal(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)

        engine.submit_proposal(sid, "agenta", architecture="Arch A")
        engine.submit_proposal(sid, "agentb", architecture="Arch B")

        with pytest.raises(ValueError, match="not found in current round"):
            engine.submit_challenge(
                sid, "agenta", "agentb", "nonexistent_id",
                risks=["Risk 1"], missing_considerations=["Missing 1"],
            )

    def test_cannot_challenge_nonexistent_agent(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)

        engine.submit_proposal(sid, "agenta", architecture="Arch A")
        engine.submit_proposal(sid, "agentb", architecture="Arch B")

        session = engine.store.get_session(sid)
        proposal_b = [p for p in session.proposals if p.agent_id == "agentb"][0]

        with pytest.raises(ValueError, match="not registered"):
            engine.submit_challenge(
                sid, "agenta", "ghost-agent", proposal_b.proposal_id,
                risks=["Risk 1"], missing_considerations=["Missing 1"],
            )


class TestChallengePriorityEnum:
    def test_priority_enum_values(self):
        assert ChallengePriority.LOW.value == "low"
        assert ChallengePriority.MEDIUM.value == "medium"
        assert ChallengePriority.HIGH.value == "high"
        assert ChallengePriority.CRITICAL.value == "critical"

    def test_challenge_uses_priority_enum(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)

        engine.submit_proposal(sid, "agenta", architecture="Arch A")
        engine.submit_proposal(sid, "agentb", architecture="Arch B")

        session = engine.store.get_session(sid)
        proposal_b = [p for p in session.proposals if p.agent_id == "agentb"][0]

        challenge = engine.submit_challenge(
            sid, "agenta", "agentb", proposal_b.proposal_id,
            risks=["Risk 1", "Risk 2", "Risk 3"],
            missing_considerations=["Missing 1", "Missing 2"],
            priority="critical",
        )
        assert challenge.priority == ChallengePriority.CRITICAL


class TestHumanOverrideStateCheck:
    def test_cannot_override_archived_session(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        # 完成并归档
        session = engine.store.get_session(sid)
        session.status = SessionStatus.COMPLETED
        session.completed_at = "2026-01-01T00:00:00"
        engine.store.update_session(session)
        engine.archive_session(sid)

        with pytest.raises(ValueError, match="Cannot override an archived"):
            engine.human_override(sid, "human", "decision", "rationale")


class TestClarityRewriteAutoAdvance:
    def test_clarify_rewrite_waits_for_human_approval(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)

        # 两个 agent 提交假设
        engine.submit_assumptions(
            sid, "agenta", [{"dimension": "core_entities", "assumption": "A1"}]
        )
        engine.submit_assumptions(
            sid, "agentb", [{"dimension": "core_entities", "assumption": "B1"}]
        )

        # 自动推进到 CLARIFY_REFINE
        session = engine.store.get_session(sid)
        assert session.current_phase == DebatePhase.CLARIFY_REFINE

        # 补充选项
        engine.supplement_assumption_options(sid, "agenta", [])
        engine.supplement_assumption_options(sid, "agentb", [])

        # 推进到 CLARIFY_REVIEW
        session = engine.store.get_session(sid)
        assert session.current_phase == DebatePhase.CLARIFY_REVIEW

        # 人类审查假设
        engine.review_assumptions(sid, [])

        # 推进到 CLARIFY_REWRITE
        session = engine.store.get_session(sid)
        assert session.current_phase == DebatePhase.CLARIFY_REWRITE

        # 两个 agent 提交精炼需求
        engine.submit_refined_requirement(sid, "agenta", "Refined requirement A")
        engine.submit_refined_requirement(sid, "agentb", "Refined requirement B")

        # 应该进入 HUMAN_REVIEW 而不是 PROPOSAL
        session = engine.store.get_session(sid)
        assert session.status == SessionStatus.HUMAN_REVIEW
        assert session.current_phase == DebatePhase.CLARIFY_REWRITE


class TestGenerateDesignDocumentStateCheck:
    def test_document_generation_for_created_session(self, engine, session_with_agents):
        """document.py 不检查状态，空 session 仍能生成包含标题的文档"""
        sid = session_with_agents.session_id
        session = engine.store.get_session(sid)
        result = generate_design_document(session)
        assert "Test Session" in result

    def test_server_rejects_created_status(self, engine):
        """server.py 的 generate_design_document 在 CREATED 状态返回提示"""
        import designdoc_mcp.server as server_module
        session = engine.create_session(title="Server Test", description="Test")
        # 注入测试 store 到 server 模块全局变量
        server_module._store = engine.store
        result = server_module.generate_design_document(session.session_id)
        assert "not found" not in result.lower()
        assert "complete the debate" in result.lower() or "CREATED" in result


class TestDocumentEmptyArchitecture:
    def test_empty_architecture_shows_placeholder(self):
        session = Session(session_id="test", title="Test", description="Desc")
        doc = generate_design_document(session)
        assert "待辩论完成后生成" in doc

    def test_invalid_insert_replaced(self):
        """验证 _add_goals_and_constraints 中不再有无效的 insert 操作"""
        import inspect
        from designdoc_mcp.document import _add_goals_and_constraints
        source = inspect.getsource(_add_goals_and_constraints)
        assert "lines.insert" not in source
        assert "sum(1 for _ in ())" not in source


# ==================== 集成测试：完整辩论流程 ====================


class TestFullDebateFlow:
    def test_full_flow_with_clarification(self, engine):
        """测试完整的澄清→辩论→共识流程"""
        # 创建 session
        session = engine.create_session(title="Full Flow Test", description="Integration test")
        sid = session.session_id

        # 注册 agents（不带 model，agent_id = name.lower()）
        engine.register_agent(sid, name="Alpha")
        engine.register_agent(sid, name="Beta")

        # 提交需求
        req = engine.submit_requirement(
            sid,
            problem_statement="Build a user management system with authentication",
            constraints=["Must use JWT"],
            acceptance_criteria=["Users can login"],
        )
        assert req.clarity_score >= 0
        assert req.clarity_dimensions is not None

        # 跳过澄清（直接进入辩论）
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)

        # PROPOSAL 阶段
        session = engine.store.get_session(sid)
        assert session.current_phase == DebatePhase.PROPOSAL

        engine.submit_proposal(sid, "alpha", architecture="Microservices arch")
        engine.submit_proposal(sid, "beta", architecture="Monolith arch")

        # CRITIC 阶段
        session = engine.store.get_session(sid)
        assert session.current_phase == DebatePhase.CRITIC

        session = engine.store.get_session(sid)
        proposal_beta = [p for p in session.proposals if p.agent_id == "beta"][0]
        proposal_alpha = [p for p in session.proposals if p.agent_id == "alpha"][0]

        engine.submit_challenge(
            sid, "alpha", "beta", proposal_beta.proposal_id,
            risks=["Risk 1", "Risk 2", "Risk 3"],
            missing_considerations=["Missing 1", "Missing 2"],
        )
        engine.submit_challenge(
            sid, "beta", "alpha", proposal_alpha.proposal_id,
            risks=["Risk A", "Risk B", "Risk C"],
            missing_considerations=["Missing A", "Missing B"],
        )

        # REVISION 阶段
        session = engine.store.get_session(sid)
        assert session.current_phase == DebatePhase.REVISION

        engine.submit_revision(
            sid, "alpha",
            accepted_feedback=["Risk 1"],
            rejected_feedback=["Risk 2"],
            rejection_reasons=["Not applicable"],
            changed_design="Revised architecture with caching",
        )
        engine.submit_revision(
            sid, "beta",
            accepted_feedback=["Risk A"],
            rejected_feedback=["Risk B"],
            rejection_reasons=["Out of scope"],
            changed_design="Revised monolith with modules",
        )

        # OPTIMIZATION 阶段
        session = engine.store.get_session(sid)
        assert session.current_phase == DebatePhase.OPTIMIZATION

        engine.submit_optimization(sid, "alpha", description="Add caching layer")
        engine.submit_optimization(sid, "beta", description="Simplify module structure")

        # DEVILS_ADVOCATE 阶段
        session = engine.store.get_session(sid)
        assert session.current_phase == DebatePhase.DEVILS_ADVOCATE

        da_agent = session.devils_advocate_agent
        engine.submit_devils_advocate(
            sid, da_agent,
            failure_modes=["Single point of failure"],
            risk_score=0.6,
        )

        # CONSENSUS 阶段
        session = engine.store.get_session(sid)
        assert session.current_phase == DebatePhase.CONSENSUS

        engine.cast_consensus_vote(sid, "alpha", VoteType.AGREE, "Good design")
        engine.cast_consensus_vote(sid, "beta", VoteType.AGREE, "Looks solid")

        # 验证完成
        session = engine.store.get_session(sid)
        assert session.status == SessionStatus.COMPLETED

        # 生成文档
        doc = generate_design_document(session)
        assert "Full Flow Test" in doc
        assert "Final Architecture" in doc


# ==================== 新功能测试 ====================


class TestAutoRejoin:
    def test_register_with_identity_creates_new(self, engine):
        session = engine.create_session(title="Rejoin Test", description="Test")
        sid = session.session_id
        r = engine.register_agent(session_id=sid, name="Cursor Agent", agent_identity="cursor_local", client_type="cursor")
        assert r.agent_id is not None
        assert getattr(r, "_rejoined", False) is False

    def test_register_same_identity_rejoins(self, engine):
        session = engine.create_session(title="Rejoin Test", description="Test")
        sid = session.session_id
        r1 = engine.register_agent(session_id=sid, name="Cursor Agent", agent_identity="cursor_local", client_type="cursor")
        r2 = engine.register_agent(session_id=sid, name="Cursor Agent", agent_identity="cursor_local", client_type="cursor")
        assert getattr(r2, "_rejoined", False) is True
        s = engine._get(sid)
        assert len(s.agents) == 1

    def test_rejoin_preserves_perspective(self, engine):
        session = engine.create_session(title="Rejoin Test", description="Test")
        sid = session.session_id
        r1 = engine.register_agent(session_id=sid, name="Cursor Agent", agent_identity="cursor_local", client_type="cursor")
        r1.current_perspective = "scalability"
        engine.store.update_session(engine._get(sid))
        r2 = engine.register_agent(session_id=sid, name="Cursor Agent", agent_identity="cursor_local", client_type="cursor")
        assert r2.current_perspective == "scalability"


class TestDecisionPoints:
    def test_submit_decision_points(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)
        engine.submit_proposal(sid, "agenta", architecture="Arch A")
        engine.submit_proposal(sid, "agentb", architecture="Arch B")

        result = engine.submit_decision_points(
            sid, "agenta",
            decision_points=[
                {
                    "topic": "database",
                    "description": "Choose database type",
                    "options": [
                        {"label": "PostgreSQL", "reasoning": "Vector support", "pros": ["Feature rich"], "cons": ["Heavy"]},
                        {"label": "SQLite", "reasoning": "Lightweight", "pros": ["Simple"], "cons": ["Limited"]},
                    ],
                    "constraints": ["SQLite conflicts with vector search"],
                }
            ],
        )
        assert result["count"] == 1

    def test_resolve_decision_point(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)
        engine.submit_proposal(sid, "agenta", architecture="Arch A")
        engine.submit_proposal(sid, "agentb", architecture="Arch B")

        dp_result = engine.submit_decision_points(
            sid, "agenta",
            decision_points=[
                {"topic": "database", "description": "Choose DB", "options": [{"label": "PostgreSQL", "reasoning": "Vector support"}]},
            ],
        )
        dp_id = dp_result["decision_ids"][0]
        # Get the actual option_id from the decision point
        session = engine._get(sid)
        dp = [d for d in session.decision_points if d.decision_id == dp_id][0]
        option_id = dp.options[0].option_id
        result = engine.resolve_decision_point(sid, dp_id, choice=option_id)
        assert result["choice"] == option_id

    def test_resolve_decision_point_custom(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)
        engine.submit_proposal(sid, "agenta", architecture="Arch A")
        engine.submit_proposal(sid, "agentb", architecture="Arch B")

        dp_result = engine.submit_decision_points(
            sid, "agenta",
            decision_points=[
                {"topic": "database", "description": "Choose DB", "options": [{"label": "PostgreSQL", "reasoning": "Vector support"}]},
            ],
        )
        dp_id = dp_result["decision_ids"][0]
        result = engine.resolve_decision_point(sid, dp_id, custom="Use MongoDB instead")
        assert result["choice"] == "custom"

    def test_merge_decision_points_by_topic(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)
        engine.submit_proposal(sid, "agenta", architecture="Arch A")
        engine.submit_proposal(sid, "agentb", architecture="Arch B")

        engine.submit_decision_points(
            sid, "agenta",
            decision_points=[
                {"topic": "database", "description": "Choose DB", "options": [{"label": "PostgreSQL", "reasoning": "Vector support"}]},
            ],
        )
        engine.submit_decision_points(
            sid, "agentb",
            decision_points=[
                {"topic": "database", "description": "DB selection needed", "options": [{"label": "SQLite", "reasoning": "Lightweight"}, {"label": "PostgreSQL", "reasoning": "ACID compliance"}]},
            ],
        )

        session = engine._get(sid)
        engine._merge_decision_points(session)
        # Should merge into 1 DP with 2 unique options (PostgreSQL merged, SQLite added)
        assert len(session.decision_points) == 1
        dp = session.decision_points[0]
        labels = [o.label for o in dp.options]
        assert "PostgreSQL" in labels
        assert "SQLite" in labels


class TestSessionPauseResume:
    def test_pause_and_resume(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        result = engine.pause_session(sid)
        assert result["status"] == "paused"

        session = engine._get(sid)
        assert session.status == SessionStatus.PAUSED

        result = engine.resume_session(sid)
        assert "resumed_from" in result

    def test_cannot_submit_while_paused(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)
        engine.pause_session(sid)

        with pytest.raises(ValueError, match="paused"):
            engine.submit_assumptions(sid, "agenta", [{"dimension": "core_entities", "assumption": "Test"}])

    def test_cannot_pause_archived(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        session = engine._get(sid)
        session.status = SessionStatus.COMPLETED
        session.completed_at = "2026-01-01T00:00:00"
        engine.store.update_session(session)
        engine.archive_session(sid)

        with pytest.raises(ValueError, match="Cannot pause"):
            engine.pause_session(sid)


class TestDeregisterAgent:
    def test_deregister_marks_inactive(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        result = engine.deregister_agent(sid, "agenta")
        assert result["action"] == "deregistered"

        session = engine._get(sid)
        agent = [a for a in session.agents if a.agent_id == "agenta"][0]
        assert agent.is_active is False

    def test_deregister_nonexistent_agent(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        with pytest.raises(ValueError, match="not found"):
            engine.deregister_agent(sid, "ghost-agent")


class TestDeleteSession:
    def test_delete_archived_session(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        session = engine._get(sid)
        session.status = SessionStatus.COMPLETED
        session.completed_at = "2026-01-01T00:00:00"
        engine.store.update_session(session)
        engine.archive_session(sid)

        result = engine.delete_session(sid)
        assert result["action"] == "deleted"

    def test_cannot_delete_active_session(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        with pytest.raises(ValueError, match="Only archived"):
            engine.delete_session(sid)


class TestSingleAgentSelfReview:
    def test_single_agent_can_self_challenge(self, engine):
        session = engine.create_session(title="Single Agent", description="Test")
        sid = session.session_id
        engine.register_agent(session_id=sid, name="Solo")

        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)

        engine.submit_proposal(sid, "solo", architecture="Arch Solo")

        session = engine._get(sid)
        proposal = session.proposals[0]

        # Single agent should be able to challenge own proposal
        challenge = engine.submit_challenge(
            sid, "solo", "solo", proposal.proposal_id,
            risks=["Risk 1", "Risk 2", "Risk 3"],
            missing_considerations=["Missing 1", "Missing 2"],
        )
        assert challenge is not None


class TestConsensusPaths:
    def test_abstain_leads_to_completion(self, engine):
        """1 AGREE + 1 ABSTAIN → COMPLETED"""
        session = engine.create_session(title="Abstain Test", description="Test")
        sid = session.session_id
        engine.register_agent(sid, name="Alpha")
        engine.register_agent(sid, name="Beta")

        engine.submit_requirement(sid, problem_statement="Test")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)

        engine.submit_proposal(sid, "alpha", architecture="A")
        engine.submit_proposal(sid, "beta", architecture="B")

        session = engine.store.get_session(sid)
        p_alpha = [p for p in session.proposals if p.agent_id == "alpha"][0]
        p_beta = [p for p in session.proposals if p.agent_id == "beta"][0]

        engine.submit_challenge(sid, "alpha", "beta", p_beta.proposal_id, risks=["r1", "r2", "r3"], missing_considerations=["m1", "m2"])
        engine.submit_challenge(sid, "beta", "alpha", p_alpha.proposal_id, risks=["r1", "r2", "r3"], missing_considerations=["m1", "m2"])

        engine.submit_revision(sid, "alpha", accepted_feedback=["r1"], rejected_feedback=["r2"], rejection_reasons=["no"], changed_design="A2")
        engine.submit_revision(sid, "beta", accepted_feedback=["r1"], rejected_feedback=["r2"], rejection_reasons=["no"], changed_design="B2")

        engine.submit_optimization(sid, "alpha", description="opt")
        engine.submit_optimization(sid, "beta", description="opt")

        da = engine.store.get_session(sid).devils_advocate_agent
        engine.submit_devils_advocate(sid, da, failure_modes=["f"], risk_score=0.5)

        session = engine.store.get_session(sid)
        assert session.current_phase == DebatePhase.CONSENSUS

        engine.cast_consensus_vote(sid, "alpha", VoteType.AGREE, "Yes")
        engine.cast_consensus_vote(sid, "beta", VoteType.ABSTAIN, "Pass")

        session = engine.store.get_session(sid)
        assert session.status == SessionStatus.COMPLETED

    def test_three_way_split_goes_to_human_review(self, engine):
        """1 AGREE + 1 DISAGREE + 1 NEEDS_CLARIFICATION → HUMAN_REVIEW"""
        session = engine.create_session(title="Split Test", description="Test")
        sid = session.session_id
        engine.register_agent(sid, name="Alpha")
        engine.register_agent(sid, name="Beta")
        engine.register_agent(sid, name="Gamma")

        engine.submit_requirement(sid, problem_statement="Test")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)

        engine.submit_proposal(sid, "alpha", architecture="A")
        engine.submit_proposal(sid, "beta", architecture="B")
        engine.submit_proposal(sid, "gamma", architecture="C")

        session = engine.store.get_session(sid)
        p_alpha = [p for p in session.proposals if p.agent_id == "alpha"][0]
        p_beta = [p for p in session.proposals if p.agent_id == "beta"][0]
        p_gamma = [p for p in session.proposals if p.agent_id == "gamma"][0]

        engine.submit_challenge(sid, "alpha", "beta", p_beta.proposal_id, risks=["r1", "r2", "r3"], missing_considerations=["m1", "m2"])
        engine.submit_challenge(sid, "beta", "gamma", p_gamma.proposal_id, risks=["r1", "r2", "r3"], missing_considerations=["m1", "m2"])
        engine.submit_challenge(sid, "gamma", "alpha", p_alpha.proposal_id, risks=["r1", "r2", "r3"], missing_considerations=["m1", "m2"])

        engine.submit_revision(sid, "alpha", accepted_feedback=["r1"], rejected_feedback=["r2"], rejection_reasons=["no"], changed_design="A2")
        engine.submit_revision(sid, "beta", accepted_feedback=["r1"], rejected_feedback=["r2"], rejection_reasons=["no"], changed_design="B2")
        engine.submit_revision(sid, "gamma", accepted_feedback=["r1"], rejected_feedback=["r2"], rejection_reasons=["no"], changed_design="C2")

        engine.submit_optimization(sid, "alpha", description="opt")
        engine.submit_optimization(sid, "beta", description="opt")
        engine.submit_optimization(sid, "gamma", description="opt")

        da = engine.store.get_session(sid).devils_advocate_agent
        engine.submit_devils_advocate(sid, da, failure_modes=["f"], risk_score=0.5)

        session = engine.store.get_session(sid)
        assert session.current_phase == DebatePhase.CONSENSUS

        engine.cast_consensus_vote(sid, "alpha", VoteType.AGREE, "Yes")
        engine.cast_consensus_vote(sid, "beta", VoteType.DISAGREE, "No")
        engine.cast_consensus_vote(sid, "gamma", VoteType.NEEDS_CLARIFICATION, "Maybe")

        session = engine.store.get_session(sid)
        assert session.status == SessionStatus.HUMAN_REVIEW


class TestHumanRejectReset:
    def test_reject_increments_round_and_resets_to_proposal(self, engine):
        """human_reject 后 round +1，phase 回到 PROPOSAL，status 变为 PROPOSAL"""
        session = engine.create_session(title="Reject Test", description="Test")
        sid = session.session_id
        engine.register_agent(sid, name="Alpha")
        engine.register_agent(sid, name="Beta")

        engine.submit_requirement(sid, problem_statement="Test")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)

        engine.submit_proposal(sid, "alpha", architecture="A")
        engine.submit_proposal(sid, "beta", architecture="B")

        session = engine.store.get_session(sid)
        p_alpha = [p for p in session.proposals if p.agent_id == "alpha"][0]
        p_beta = [p for p in session.proposals if p.agent_id == "beta"][0]

        engine.submit_challenge(sid, "alpha", "beta", p_beta.proposal_id, risks=["r1", "r2", "r3"], missing_considerations=["m1", "m2"])
        engine.submit_challenge(sid, "beta", "alpha", p_alpha.proposal_id, risks=["r1", "r2", "r3"], missing_considerations=["m1", "m2"])

        engine.submit_revision(sid, "alpha", accepted_feedback=["r1"], rejected_feedback=["r2"], rejection_reasons=["no"], changed_design="A2")
        engine.submit_revision(sid, "beta", accepted_feedback=["r1"], rejected_feedback=["r2"], rejection_reasons=["no"], changed_design="B2")

        engine.submit_optimization(sid, "alpha", description="opt")
        engine.submit_optimization(sid, "beta", description="opt")

        da = engine.store.get_session(sid).devils_advocate_agent
        engine.submit_devils_advocate(sid, da, failure_modes=["f"], risk_score=0.5)

        session = engine.store.get_session(sid)
        assert session.current_phase == DebatePhase.CONSENSUS

        engine.cast_consensus_vote(sid, "alpha", VoteType.AGREE, "Yes")
        engine.cast_consensus_vote(sid, "beta", VoteType.DISAGREE, "No")

        session = engine.store.get_session(sid)
        assert session.status == SessionStatus.HUMAN_REVIEW
        old_round = session.current_round

        engine.human_reject(sid, approver="human", reason="Needs more work")

        session = engine.store.get_session(sid)
        assert session.status == SessionStatus.PROPOSAL
        assert session.current_phase == DebatePhase.PROPOSAL
        assert session.current_round == old_round + 1


class TestRevertToEvent:
    def test_revert_truncates_events_and_data(self, engine):
        """回退到指定 event 后，events 和数据列表被截断"""
        session = engine.create_session(title="Revert Test", description="Test")
        sid = session.session_id
        engine.register_agent(sid, name="Alpha")
        engine.register_agent(sid, name="Beta")

        engine.submit_requirement(sid, problem_statement="Test")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)

        engine.submit_proposal(sid, "alpha", architecture="A")
        engine.submit_proposal(sid, "beta", architecture="B")

        session = engine.store.get_session(sid)
        proposals_before = len(session.proposals)
        events_before = len(session.events)
        target_event = session.events[-3]  # 回退到倒数第 3 个 event

        engine.revert_to_event(sid, target_event.event_id)

        session = engine.store.get_session(sid)
        assert len(session.events) < events_before
        assert len(session.proposals) < proposals_before
        assert all(e.created_at <= target_event.created_at for e in session.events[:-1])

    def test_revert_resets_phase_and_status(self, engine):
        """回退后 phase/round/status 重置为目标 event 对应的状态"""
        session = engine.create_session(title="Revert Phase Test", description="Test")
        sid = session.session_id
        engine.register_agent(sid, name="Alpha")
        engine.register_agent(sid, name="Beta")

        engine.submit_requirement(sid, problem_statement="Test")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)

        # 推进到 PROPOSAL 之后
        engine.submit_proposal(sid, "alpha", architecture="A")
        engine.submit_proposal(sid, "beta", architecture="B")

        session = engine.store.get_session(sid)
        assert session.current_phase == DebatePhase.CRITIC

        # 找到 PROPOSAL 阶段的最后一个 event
        proposal_events = [e for e in session.events if e.phase == DebatePhase.PROPOSAL]
        target_event = proposal_events[-1]

        engine.revert_to_event(sid, target_event.event_id)

        session = engine.store.get_session(sid)
        assert session.current_phase == DebatePhase.PROPOSAL
        assert session.current_round == target_event.round_number
        assert session.status == SessionStatus.PROPOSAL

    def test_revert_clears_derived_state(self, engine):
        """回退后派生状态被清空"""
        session = engine.create_session(title="Revert Derived Test", description="Test")
        sid = session.session_id
        engine.register_agent(sid, name="Alpha")
        engine.register_agent(sid, name="Beta")

        engine.submit_requirement(sid, problem_statement="Test")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)

        engine.submit_proposal(sid, "alpha", architecture="A")
        engine.submit_proposal(sid, "beta", architecture="B")

        session = engine.store.get_session(sid)
        target_event = session.events[-2]

        engine.revert_to_event(sid, target_event.event_id)

        session = engine.store.get_session(sid)
        assert session.merged_assumptions == []
        assert session.clarify_refine_submitted == []
        assert session.devils_advocate_agent == ""
        assert session.novelty_scores == []

    def test_revert_to_missing_event_raises(self, engine):
        """回退到不存在的 event 应该抛出 ValueError"""
        session = engine.create_session(title="Revert Error Test", description="Test")
        sid = session.session_id
        with pytest.raises(ValueError, match="not found"):
            engine.revert_to_event(sid, "nonexistent-event-id")


class TestDebatePhaseCreated:
    def test_new_session_has_created_phase(self, engine):
        session = engine.create_session(title="New Session", description="Test")
        assert session.current_phase == DebatePhase.CREATED
        assert session.status == SessionStatus.CREATED


class TestRequirementDeltaHierarchy:
    def test_requirement_delta_can_reference_parent(self, engine):
        session = engine.create_session(title="Delta Hierarchy", description="Test")
        sid = session.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")

        parent = engine.add_requirement_delta(sid, delta_statement="Add auth")
        parent_id = parent["delta_id"]

        child = engine.add_requirement_delta(sid, delta_statement="Add OAuth", parent_delta_id=parent_id)
        assert child["delta_id"] is not None

        session = engine._get(sid)
        assert len(session.requirement_deltas) == 2
        assert session.requirement_deltas[1].parent_delta_id == parent_id

    def test_invalid_parent_delta_rejected(self, engine):
        session = engine.create_session(title="Delta Invalid", description="Test")
        sid = session.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")

        with pytest.raises(ValueError, match="Parent delta 'nonexistent' not found"):
            engine.add_requirement_delta(sid, delta_statement="Add auth", parent_delta_id="nonexistent")

    def test_backward_compatibility_without_parent(self, engine):
        session = engine.create_session(title="Delta Backcompat", description="Test")
        sid = session.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")

        result = engine.add_requirement_delta(sid, delta_statement="Add auth")
        assert "delta_id" in result
        assert "delta_clarity_score" in result
        assert "combined_clarity_score" in result
        assert "action" in result

        session = engine._get(sid)
        assert len(session.requirement_deltas) == 1
        assert session.requirement_deltas[0].parent_delta_id is None

    def test_parent_chain_same_session_only(self, engine):
        session_a = engine.create_session(title="Session A", description="Test")
        session_b = engine.create_session(title="Session B", description="Test")
        sid_a = session_a.session_id
        sid_b = session_b.session_id

        engine.submit_requirement(sid_a, problem_statement="Build system A")
        engine.submit_requirement(sid_b, problem_statement="Build system B")

        parent = engine.add_requirement_delta(sid_a, delta_statement="Add auth")
        parent_id = parent["delta_id"]

        with pytest.raises(ValueError, match=f"Parent delta '{parent_id}' not found"):
            engine.add_requirement_delta(sid_b, delta_statement="Add auth", parent_delta_id=parent_id)


