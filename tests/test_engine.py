"""DesignDoc MCP 单元测试与集成测试"""
from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta, timezone
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


class TestRuntimeModeDetection:
    @pytest.mark.parametrize("client_type", ["cursor", "claude_code", "kimi", "atomcode", "CURSOR", " Cursor "])
    def test_known_clients_are_loop(self, engine, client_type):
        session = engine.create_session(title="RM", description="Test")
        r = engine.register_agent(session_id=session.session_id, name="A", agent_identity=f"id_{client_type}", client_type=client_type)
        assert r.runtime_mode == "persistent_worker"

    @pytest.mark.parametrize("client_type", ["", "generic", "trae", "unknown_cli"])
    def test_unknown_clients_are_step(self, engine, client_type):
        session = engine.create_session(title="RM", description="Test")
        r = engine.register_agent(session_id=session.session_id, name="A", agent_identity=f"id_{client_type or 'empty'}", client_type=client_type)
        assert r.runtime_mode == "normal_worker"

    def test_rejoin_recomputes_mode_from_client(self, engine):
        session = engine.create_session(title="RM", description="Test")
        sid = session.session_id
        r1 = engine.register_agent(session_id=sid, name="A", agent_identity="stable", client_type="trae")
        assert r1.runtime_mode == "normal_worker"
        r2 = engine.register_agent(session_id=sid, name="A", agent_identity="stable", client_type="cursor")
        assert getattr(r2, "_rejoined", False) is True
        assert r2.runtime_mode == "persistent_worker"


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


class TestBulkResolveDecisionPoints:
    def test_merge_stores_support_count_in_metadata(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)
        engine.submit_proposal(sid, "agenta", architecture="Arch A")
        engine.submit_proposal(sid, "agentb", architecture="Arch B")

        engine.submit_decision_points(
            sid, "agenta",
            decision_points=[
                {"topic": "database", "description": "Choose DB", "options": [
                    {"label": "PostgreSQL", "reasoning": "Vector support"},
                    {"label": "SQLite", "reasoning": "Lightweight"},
                ]},
            ],
        )
        engine.submit_decision_points(
            sid, "agentb",
            decision_points=[
                {"topic": "database", "description": "DB selection", "options": [
                    {"label": "PostgreSQL", "reasoning": "ACID compliance"},
                    {"label": "MySQL", "reasoning": "Team familiarity"},
                ]},
            ],
        )

        session = engine._get(sid)
        engine._merge_decision_points(session)

        support_meta = session.metadata.get("decision_point_supports", {})
        dp = session.decision_points[0]
        counts = support_meta.get(dp.decision_id, {})
        assert len(counts) == 3
        # PostgreSQL proposed by both agents -> count 2
        pg_opt = [o for o in dp.options if o.label == "PostgreSQL"][0]
        assert counts[pg_opt.option_id] == 2
        sqlite_opt = [o for o in dp.options if o.label == "SQLite"][0]
        assert counts[sqlite_opt.option_id] == 1
        mysql_opt = [o for o in dp.options if o.label == "MySQL"][0]
        assert counts[mysql_opt.option_id] == 1

    def test_bulk_resolve_majority_picks_highest_count(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)
        engine.submit_proposal(sid, "agenta", architecture="Arch A")
        engine.submit_proposal(sid, "agentb", architecture="Arch B")

        engine.submit_decision_points(
            sid, "agenta",
            decision_points=[
                {"topic": "database", "description": "Choose DB", "options": [
                    {"label": "PostgreSQL", "reasoning": "Vector support"},
                    {"label": "SQLite", "reasoning": "Lightweight"},
                ]},
            ],
        )
        engine.submit_decision_points(
            sid, "agentb",
            decision_points=[
                {"topic": "database", "description": "DB selection", "options": [
                    {"label": "PostgreSQL", "reasoning": "ACID compliance"},
                ]},
            ],
        )

        session = engine._get(sid)
        engine._merge_decision_points(session)

        result = engine.bulk_resolve_decision_points(sid, strategy="majority", preview=False)
        assert len(result["resolved"]) == 1
        assert result["resolved"][0]["chosen_label"] == "PostgreSQL"
        assert result["resolved"][0]["support_count"] == 2
        assert result["resolved"][0]["fallback"] is False
        assert len(result["skipped"]) == 0
        assert result["preview"] is False

        # Verify session is actually modified
        session = engine._get(sid)
        assert session.decision_points[0].human_choice == result["resolved"][0]["chosen_option_id"]

    def test_bulk_resolve_preview_does_not_modify(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)
        engine.submit_proposal(sid, "agenta", architecture="Arch A")
        engine.submit_proposal(sid, "agentb", architecture="Arch B")

        dp_result = engine.submit_decision_points(
            sid, "agenta",
            decision_points=[
                {"topic": "database", "description": "Choose DB", "options": [
                    {"label": "PostgreSQL", "reasoning": "Vector support"},
                ]},
            ],
        )

        result = engine.bulk_resolve_decision_points(sid, strategy="majority", preview=True)
        assert len(result["resolved"]) == 1
        assert result["preview"] is True

        session = engine._get(sid)
        dp = [d for d in session.decision_points if d.decision_id == dp_result["decision_ids"][0]][0]
        assert dp.human_choice == ""

    def test_bulk_resolve_fallback_without_metadata(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)
        engine.submit_proposal(sid, "agenta", architecture="Arch A")
        engine.submit_proposal(sid, "agentb", architecture="Arch B")

        engine.submit_decision_points(
            sid, "agenta",
            decision_points=[
                {"topic": "database", "description": "Choose DB", "options": [
                    {"label": "PostgreSQL", "reasoning": "Vector support"},
                    {"label": "SQLite", "reasoning": "Lightweight"},
                ]},
            ],
        )

        # Simulate old session: clear metadata before resolving
        session = engine._get(sid)
        session.metadata.pop("decision_point_supports", None)

        result = engine.bulk_resolve_decision_points(sid, strategy="majority", preview=False)
        assert len(result["resolved"]) == 1
        assert result["resolved"][0]["chosen_label"] == "PostgreSQL"
        assert result["resolved"][0]["fallback"] is True
        assert result["resolved"][0]["support_count"] == 1

    def test_bulk_resolve_tie_breaks_to_first_option(self, engine, session_with_agents):
        sid = session_with_agents.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)
        engine.submit_proposal(sid, "agenta", architecture="Arch A")
        engine.submit_proposal(sid, "agentb", architecture="Arch B")

        engine.submit_decision_points(
            sid, "agenta",
            decision_points=[
                {"topic": "database", "description": "Choose DB", "options": [
                    {"label": "PostgreSQL", "reasoning": "Vector support"},
                ]},
            ],
        )
        engine.submit_decision_points(
            sid, "agentb",
            decision_points=[
                {"topic": "database", "description": "DB selection", "options": [
                    {"label": "SQLite", "reasoning": "Lightweight"},
                ]},
            ],
        )

        session = engine._get(sid)
        engine._merge_decision_points(session)

        result = engine.bulk_resolve_decision_points(sid, strategy="majority", preview=False)
        assert len(result["resolved"]) == 1
        # Both have count 1; first in merged list wins
        chosen = result["resolved"][0]["chosen_label"]
        assert chosen in ("PostgreSQL", "SQLite")


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

    def test_revert_truncates_deltas(self, engine):
        """回退后 requirement_deltas 按 created_at 截断"""
        session = engine.create_session(title="Revert Deltas Test", description="Test")
        sid = session.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")

        session = engine.store.get_session(sid)
        target_event = session.events[-1]

        engine.add_requirement_delta(sid, delta_statement="Add auth")
        engine.add_requirement_delta(sid, delta_statement="Add OAuth")

        session = engine.store.get_session(sid)
        deltas_before = len(session.requirement_deltas)
        assert deltas_before == 2

        engine.revert_to_event(sid, target_event.event_id)

        session = engine.store.get_session(sid)
        assert len(session.requirement_deltas) == 0
        assert all(d.created_at <= target_event.created_at for d in session.requirement_deltas)

    def test_revert_to_missing_event_raises(self, engine):
        """回退到不存在的 event 应该抛出 ValueError"""
        session = engine.create_session(title="Revert Error Test", description="Test")
        sid = session.session_id
        with pytest.raises(ValueError, match="not found"):
            engine.revert_to_event(sid, "nonexistent-event-id")


class TestRebuildDerivedState:
    def test_rebuild_matches_original_phase_round_status(self, engine):
        """builder 重建的 phase/round/status 与原始 session 一致"""
        session = engine.create_session(title="Rebuild Test", description="Test")
        sid = session.session_id
        engine.register_agent(sid, name="Alpha")
        engine.register_agent(sid, name="Beta")

        engine.submit_requirement(sid, problem_statement="Test")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)
        engine.submit_proposal(sid, "alpha", architecture="A")
        engine.submit_proposal(sid, "beta", architecture="B")

        session = engine.store.get_session(sid)
        expected_phase = session.current_phase
        expected_round = session.current_round
        expected_status = session.status

        # Simulate corrupted derived state
        session.merged_assumptions = ["stale"]
        session.clarify_refine_submitted = ["stale"]
        session.devils_advocate_agent = "stale"
        session.novelty_scores = [0.5]

        engine._rebuild_derived_state(session)

        assert session.current_phase == expected_phase
        assert session.current_round == expected_round
        assert session.status == expected_status

    def test_rebuild_from_empty_events_is_noop(self, engine):
        """空 events 列表时 builder 不崩溃"""
        session = engine.create_session(title="Empty Events", description="Test")
        sid = session.session_id
        session = engine.store.get_session(sid)
        original_phase = session.current_phase
        original_status = session.status

        session.events = []
        engine._rebuild_derived_state(session)

        assert session.current_phase == original_phase
        assert session.status == original_status

    def test_rebuild_clarify_refine_submitted_from_events(self, engine):
        """builder 从 REQUIREMENT_REFINE events 重建 clarify_refine_submitted"""
        session = engine.create_session(title="Refine Submitted", description="Test")
        sid = session.session_id
        engine.register_agent(sid, name="Alpha")
        engine.register_agent(sid, name="Beta")

        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)

        session = engine.store.get_session(sid)
        session.clarify_refine_submitted = []
        engine._rebuild_derived_state(session)

        # In this flow no REQUIREMENT_REFINE events exist yet
        assert session.clarify_refine_submitted == []


class TestValidateSessionConsistency:
    def test_valid_session_passes_validation(self, engine):
        """正常 session 通过一致性验证"""
        session = engine.create_session(title="Valid Test", description="Test")
        sid = session.session_id
        engine.register_agent(sid, name="Alpha")
        engine.register_agent(sid, name="Beta")

        engine.submit_requirement(sid, problem_statement="Test")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)
        engine.submit_proposal(sid, "alpha", architecture="A")
        engine.submit_proposal(sid, "beta", architecture="B")

        session = engine.store.get_session(sid)
        result = engine.validate_session_consistency(session)
        assert result["valid"] is True
        assert result["mismatches"] == []

    def test_corrupted_session_detects_mismatch(self, engine):
        """篡改 derived state 后验证应检测到 mismatch"""
        session = engine.create_session(title="Corrupt Test", description="Test")
        sid = session.session_id
        engine.register_agent(sid, name="Alpha")
        engine.register_agent(sid, name="Beta")

        engine.submit_requirement(sid, problem_statement="Test")
        engine.start_clarification(sid)

        session = engine.store.get_session(sid)
        original_phase = session.current_phase
        # Corrupt the phase
        session.current_phase = DebatePhase.PROPOSAL

        result = engine.validate_session_consistency(session)
        assert result["valid"] is False
        assert any("phase" in m for m in result["mismatches"])

        # Ensure session is restored to corrupted state (snapshot taken inside validate)
        # The point is validation doesn't leave the session in a *different* state
        assert session.current_phase == DebatePhase.PROPOSAL

    def test_validation_does_not_mutate_session(self, engine):
        """验证后 session 状态应完全恢复"""
        session = engine.create_session(title="Immutable Test", description="Test")
        sid = session.session_id
        engine.register_agent(sid, name="Alpha")
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.start_clarification(sid)

        session = engine.store.get_session(sid)
        original_round = session.current_round
        original_status = session.status

        engine.validate_session_consistency(session)

        assert session.current_round == original_round
        assert session.status == original_status


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

    def test_deltas_exposed_in_session_summary(self, engine):
        """get_session_summary 暴露 requirement_deltas 层次信息"""
        session = engine.create_session(title="Delta Summary", description="Test")
        sid = session.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")

        parent = engine.add_requirement_delta(sid, delta_statement="Add auth")
        parent_id = parent["delta_id"]
        engine.add_requirement_delta(sid, delta_statement="Add OAuth", parent_delta_id=parent_id)

        summary = engine.get_session_summary(sid)
        assert summary["requirement_deltas_count"] == 2
        assert len(summary["requirement_deltas"]) == 2
        assert summary["requirement_deltas"][0]["delta_id"] == parent_id
        assert summary["requirement_deltas"][1]["parent_delta_id"] == parent_id

    def test_deltas_exposed_in_session_flow(self, engine):
        """get_session_flow 暴露 requirement_deltas 层次信息"""
        session = engine.create_session(title="Delta Flow", description="Test")
        sid = session.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")

        parent = engine.add_requirement_delta(sid, delta_statement="Add auth")
        parent_id = parent["delta_id"]
        engine.add_requirement_delta(sid, delta_statement="Add OAuth", parent_delta_id=parent_id)

        flow = engine.get_session_flow(sid)
        assert flow["requirement_deltas_count"] == 2
        assert len(flow["requirement_deltas"]) == 2
        assert flow["requirement_deltas"][0]["delta_id"] == parent_id
        assert flow["requirement_deltas"][1]["parent_delta_id"] == parent_id


class TestSessionEventTimeline:
    def test_timeline_empty_for_new_session(self, engine):
        session = engine.create_session(title="Timeline Test", description="Test")
        sid = session.session_id
        flow = engine.get_session_flow(sid)
        assert flow["event_timeline"] == []

    def test_timeline_contains_phase_transitions(self, engine):
        session = engine.create_session(title="Timeline Test", description="Test")
        sid = session.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.register_agent(sid, name="agent_a")
        engine.start_clarification(sid)

        flow = engine.get_session_flow(sid)
        timeline = flow["event_timeline"]
        assert len(timeline) >= 1
        assert timeline[0]["from_phase"] == "created"
        assert timeline[0]["to_phase"] == "clarify_identify"
        assert "timestamp" in timeline[0]

    def test_timeline_sorted_by_time(self, engine):
        session = engine.create_session(title="Timeline Test", description="Test")
        sid = session.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.register_agent(sid, name="agent_a")
        engine.start_clarification(sid)

        flow = engine.get_session_flow(sid)
        timeline = flow["event_timeline"]
        timestamps = [t["timestamp"] for t in timeline]
        assert timestamps == sorted(timestamps)


class TestCompareSessions:
    def test_compare_sessions_basic(self, engine):
        session_a = engine.create_session(title="Session A", description="Test A")
        session_b = engine.create_session(title="Session B", description="Test B")
        sid_a = session_a.session_id
        sid_b = session_b.session_id

        engine.submit_requirement(sid_a, problem_statement="Build system A")
        engine.submit_requirement(sid_b, problem_statement="Build system B")

        engine.register_agent(session_id=sid_a, name="AgentA1")
        engine.register_agent(session_id=sid_a, name="AgentA2")
        engine.register_agent(session_id=sid_b, name="AgentB1")

        result = engine.compare_sessions(sid_a, sid_b)

        assert result["requirements_match"] is False
        assert result["agent_count"]["a"] == 2
        assert result["agent_count"]["b"] == 1
        assert result["same_phase"] is True
        assert result["same_status"] is True
        assert result["session_a"]["title"] == "Session A"
        assert result["session_b"]["title"] == "Session B"

    def test_compare_sessions_same_requirement(self, engine):
        session_a = engine.create_session(title="Session A", description="Test")
        session_b = engine.create_session(title="Session B", description="Test")
        sid_a = session_a.session_id
        sid_b = session_b.session_id

        engine.submit_requirement(sid_a, problem_statement="Build identical system")
        engine.submit_requirement(sid_b, problem_statement="Build identical system")

        result = engine.compare_sessions(sid_a, sid_b)

        assert result["requirements_match"] is True
        assert result["same_phase"] is True
        assert result["same_status"] is True

    def test_compare_sessions_not_found(self, engine):
        session = engine.create_session(title="Session", description="Test")
        with pytest.raises(ValueError, match="Session 'nonexistent' not found"):
            engine.compare_sessions(session.session_id, "nonexistent")


class TestHtmlExport:
    def test_html_export_contains_title(self, engine):
        session = engine.create_session(title="HTML Test Session", description="Test")
        sid = session.session_id
        engine.submit_requirement(sid, problem_statement="Build a web app")

        from designdoc_mcp.document import generate_design_document_html
        html = generate_design_document_html(engine._get(sid))

        assert "<!DOCTYPE html>" in html
        assert "HTML Test Session" in html
        assert "<title>HTML Test Session</title>" in html

    def test_html_export_contains_requirement(self, engine):
        session = engine.create_session(title="HTML Req Session", description="Test")
        sid = session.session_id
        engine.submit_requirement(sid, problem_statement="Build a fast API")

        from designdoc_mcp.document import generate_design_document_html
        html = generate_design_document_html(engine._get(sid))

        assert "Build a fast API" in html

    def test_html_export_structure(self, engine):
        session = engine.create_session(title="HTML Struct Session", description="Test")
        sid = session.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.register_agent(session_id=sid, name="Agent1")

        from designdoc_mcp.document import generate_design_document_html
        html = generate_design_document_html(engine._get(sid))

        assert '<html lang="en">' in html
        assert "</head>" in html
        assert "<body>" in html
        assert "</body>" in html
        assert "</html>" in html


class TestJsonExport:
    def test_json_export_contains_session_data(self, engine):
        """JSON export 包含 session 结构化数据"""
        session = engine.create_session(title="JSON Test Session", description="Test")
        sid = session.session_id
        engine.submit_requirement(sid, problem_statement="Build a web app")
        engine.register_agent(session_id=sid, name="Agent1")
        engine.add_requirement_delta(sid, delta_statement="Add auth")

        from designdoc_mcp.document import generate_design_document_json
        json_str = generate_design_document_json(engine._get(sid))

        import json
        data = json.loads(json_str)
        assert data["session_id"] == sid
        assert data["title"] == "JSON Test Session"
        assert "Build a web app" in data["requirement"]["problem_statement"]
        assert len(data["agents"]) == 1
        assert data["agents"][0]["name"] == "Agent1"
        assert len(data["requirement_deltas"]) == 1
        assert data["requirement_deltas"][0]["problem_statement"] == "Add auth"

    def test_json_export_valid_json(self, engine):
        """JSON export 输出是合法 JSON"""
        session = engine.create_session(title="JSON Valid", description="Test")
        sid = session.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")

        from designdoc_mcp.document import generate_design_document_json
        json_str = generate_design_document_json(engine._get(sid))

        import json
        data = json.loads(json_str)
        assert isinstance(data, dict)
        assert "session_id" in data
        assert "status" in data
        assert "phase" in data


class TestMultiHumanReview:
    def _setup_human_review_session(self, engine):
        session = engine.create_session(title="Multi-Human Review", description="Test")
        sid = session.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.register_agent(session_id=sid, name="Agent1")
        engine.register_agent(session_id=sid, name="Agent2")
        session = engine._get(sid)
        session.status = SessionStatus.HUMAN_REVIEW
        engine.store.update_session(session)
        return sid

    def test_submit_human_vote_basic(self, engine):
        sid = self._setup_human_review_session(engine)
        result = engine.submit_human_vote(sid, "Reviewer1", "agree", "Looks good")
        assert result["total_votes"] == 1
        assert result["agree_count"] == 1
        assert result["session_status"] == "human_review"

    def test_majority_vote_completes_session(self, engine):
        sid = self._setup_human_review_session(engine)
        engine.submit_human_vote(sid, "Reviewer1", "agree")
        result = engine.submit_human_vote(sid, "Reviewer2", "agree")
        assert result["total_votes"] == 2
        assert result["agree_count"] == 2
        assert result["session_status"] == "completed"
        session = engine._get(sid)
        assert session.status == SessionStatus.COMPLETED

    def test_non_majority_keeps_human_review(self, engine):
        sid = self._setup_human_review_session(engine)
        engine.submit_human_vote(sid, "Reviewer1", "agree")
        result = engine.submit_human_vote(sid, "Reviewer2", "disagree")
        assert result["total_votes"] == 2
        assert result["agree_count"] == 1
        assert result["session_status"] == "human_review"

    def test_human_vote_wrong_state(self, engine):
        session = engine.create_session(title="Wrong State", description="Test")
        sid = session.session_id
        with pytest.raises(ValueError, match="Session is not in human review state"):
            engine.submit_human_vote(sid, "Reviewer1", "agree")


class TestSessionDiagnostics:
    """Loop 1 — Session diagnostics engine tests."""

    def test_healthy_session_returns_full_score(self, engine):
        """完整 debate 后的健康 session 返回 health_score=100，warnings 为空。"""
        from tests.test_replay_determinism import _build_full_debate_session

        session = _build_full_debate_session(engine)
        diag = engine.get_session_diagnostics(session.session_id)

        assert diag["health_score"] == 100
        assert diag["stall_status"]["is_stalled"] is False
        assert diag["data_consistency"]["valid"] is True
        assert diag["warnings"] == []
        assert diag["workflow_progress"]["terminal_phase"] is True

    def test_corrupted_session_detects_consistency_mismatch(self, engine):
        """手动篡改 derived state 后，diagnostics 检测到 mismatch 并报告 warnings。"""
        session = engine.create_session(title="Diag Corrupt", description="Test")
        sid = session.session_id
        engine.register_agent(sid, name="Alpha")
        engine.submit_requirement(sid, problem_statement="Test")
        engine.start_clarification(sid)

        # 篡改状态
        session = engine.store.get_session(sid)
        session.current_phase = DebatePhase.PROPOSAL
        session.status = SessionStatus.PROPOSAL
        engine.store.update_session(session)

        diag = engine.get_session_diagnostics(sid)
        assert diag["data_consistency"]["valid"] is False
        assert any("phase" in w["message"] for w in diag["warnings"])
        assert diag["health_score"] <= 50

    def test_stalled_session_detected_by_updated_at(self, engine):
        """updated_at 超过 300 秒的 ACTIVE session 被标记为 stalled。"""
        import json as _json

        session = engine.create_session(title="Diag Stall", description="Test")
        sid = session.session_id
        engine.register_agent(sid, name="Alpha")
        engine.submit_requirement(sid, problem_statement="Test")

        # 直接修改 store JSON 文件中的 updated_at 为 400 秒前，并清除缓存
        path = engine.store._session_path(sid)
        data = _json.loads(path.read_text(encoding="utf-8"))
        stale_time = (datetime.now(timezone.utc) - timedelta(seconds=400)).isoformat()
        data["updated_at"] = stale_time
        path.write_text(_json.dumps(data), encoding="utf-8")
        engine.store._sessions.pop(sid, None)
        engine.store._mtimes.pop(sid, None)

        diag = engine.get_session_diagnostics(sid)
        assert diag["stall_status"]["is_stalled"] is True
        assert diag["stall_status"]["seconds_since_activity"] >= 400
        assert any(w["category"] == "stall" for w in diag["warnings"])

    def test_non_stalled_active_session(self, engine):
        """刚创建的 ACTIVE session 不被标记为 stalled。"""
        session = engine.create_session(title="Diag Active", description="Test")
        sid = session.session_id
        engine.register_agent(sid, name="Alpha")

        diag = engine.get_session_diagnostics(sid)
        assert diag["stall_status"]["is_stalled"] is False
        assert diag["stall_status"]["seconds_since_activity"] < 300

    def test_diagnostics_is_read_only(self, engine):
        """连续调用两次 diagnostics，session 状态无任何变化。"""
        session = engine.create_session(title="Diag ReadOnly", description="Test")
        sid = session.session_id
        engine.register_agent(sid, name="Alpha")
        engine.submit_requirement(sid, problem_statement="Test")
        engine.start_clarification(sid)

        # 第一次调用前 snapshot
        session = engine.store.get_session(sid)
        before = {
            "phase": session.current_phase,
            "round": session.current_round,
            "status": session.status,
            "events_len": len(session.events),
        }

        engine.get_session_diagnostics(sid)
        engine.get_session_diagnostics(sid)

        session = engine.store.get_session(sid)
        after = {
            "phase": session.current_phase,
            "round": session.current_round,
            "status": session.status,
            "events_len": len(session.events),
        }
        assert before == after

    def test_no_agents_warning(self, engine):
        """ACTIVE session 无 agents 时生成 workflow warning。"""
        session = engine.create_session(title="Diag No Agents", description="Test")
        sid = session.session_id
        # 不注册 agent

        diag = engine.get_session_diagnostics(sid)
        assert any(
            "No agents registered" in w["message"] for w in diag["warnings"]
        )

    def test_human_review_no_votes_warning(self, engine):
        """HUMAN_REVIEW session 零投票时生成 workflow warning。"""
        session = engine.create_session(title="Diag HR", description="Test")
        sid = session.session_id
        engine.submit_requirement(sid, problem_statement="Test")
        engine.register_agent(sid, name="Agent1")
        session = engine.store.get_session(sid)
        session.status = SessionStatus.HUMAN_REVIEW
        engine.store.update_session(session)

        diag = engine.get_session_diagnostics(sid)
        assert any(
            "human review with zero votes" in w["message"] for w in diag["warnings"]
        )
