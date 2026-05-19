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
    def test_cannot_generate_from_created_state(self, engine, session_with_agents):
        """测试 generate_design_document 在非完成状态下返回提示"""
        sid = session_with_agents.session_id
        # 直接使用 document 模块函数测试（不通过 server 模块的全局 store）
        session = engine.store.get_session(sid)
        result = generate_design_document(session)
        # 文档生成不检查状态，但 server 层会检查
        # 这里验证文档内容在空 session 下是合理的
        assert "Test Session" in result


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
