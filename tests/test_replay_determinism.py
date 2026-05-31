"""Replay determinism regression suite for Phase C.

验证 session 的 derived state 可以从 event stream 中确定性重建，
覆盖完整辩论生命周期、多轮 human review 和带 undo 的 session。
"""
from __future__ import annotations

import copy

import pytest

from designdoc_mcp.engine import CollaborationEngine
from designdoc_mcp.models import DebatePhase, EventType, SessionStatus, VoteType
from designdoc_mcp.store import SessionStore


@pytest.fixture
def tmp_store(tmp_path):
    return SessionStore(data_dir=str(tmp_path))


@pytest.fixture
def engine(tmp_store):
    return CollaborationEngine(tmp_store)


def _snapshot_derived(session):
    """提取 session 的派生状态快照（值类型，可深度比较）。"""
    return {
        "current_phase": session.current_phase,
        "current_round": session.current_round,
        "status": session.status,
        "clarify_refine_submitted": list(session.clarify_refine_submitted),
        "merged_assumptions": list(session.merged_assumptions),
        "devils_advocate_agent": session.devils_advocate_agent,
        "novelty_scores": list(session.novelty_scores),
        "completed_at": session.completed_at,
        "archived_at": session.archived_at,
    }


def _restore_derived(session, snapshot):
    """将派生状态快照写回 session。"""
    session.current_phase = snapshot["current_phase"]
    session.current_round = snapshot["current_round"]
    session.status = snapshot["status"]
    session.clarify_refine_submitted = snapshot["clarify_refine_submitted"]
    session.merged_assumptions = snapshot["merged_assumptions"]
    session.devils_advocate_agent = snapshot["devils_advocate_agent"]
    session.novelty_scores = snapshot["novelty_scores"]
    session.completed_at = snapshot["completed_at"]
    session.archived_at = snapshot["archived_at"]


def _run_replay(engine: CollaborationEngine, session) -> dict:
    """对 session 执行一次 replay，返回派生状态快照。"""
    engine._rebuild_derived_state(session)
    return _snapshot_derived(session)


def _assert_replay_determinism(engine: CollaborationEngine, session):
    """断言对同一 session replay 两次结果完全一致（bit-identical）。"""
    original = _snapshot_derived(session)

    # 第一次 replay：先 corrupt 再 rebuild，确保不是 no-op
    session.current_phase = DebatePhase.CREATED
    session.current_round = 0
    session.status = SessionStatus.CREATED
    result1 = _run_replay(engine, session)

    # 恢复原始状态
    _restore_derived(session, original)

    # 第二次 replay
    session.current_phase = DebatePhase.CREATED
    session.current_round = 0
    session.status = SessionStatus.CREATED
    result2 = _run_replay(engine, session)

    assert result1 == result2, f"Replay non-deterministic: {result1} != {result2}"

    # 额外验证：replay 结果与原始状态一致
    assert result1["current_phase"] == original["current_phase"]
    assert result1["current_round"] == original["current_round"]
    assert result1["status"] == original["status"]
    assert result1["clarify_refine_submitted"] == original["clarify_refine_submitted"]


def _build_full_debate_session(engine: CollaborationEngine):
    """构建一个走完完整 debate lifecycle 的 session。"""
    session = engine.create_session(
        title="Replay Determinism Full Flow", description="Test"
    )
    sid = session.session_id

    engine.register_agent(sid, name="Alpha")
    engine.register_agent(sid, name="Beta")

    engine.submit_requirement(
        sid,
        problem_statement="Build a scalable queue system",
        constraints=["Must support FIFO"],
        acceptance_criteria=["Throughput > 1k msg/s"],
    )

    engine.start_clarification(sid)
    engine.force_skip_clarification(sid)

    # PROPOSAL
    engine.submit_proposal(sid, "alpha", architecture="Event-driven microservices")
    engine.submit_proposal(sid, "beta", architecture="Single-process with async I/O")

    # CRITIC
    session = engine.store.get_session(sid)
    proposal_beta = [p for p in session.proposals if p.agent_id == "beta"][0]
    proposal_alpha = [p for p in session.proposals if p.agent_id == "alpha"][0]

    engine.submit_challenge(
        sid, "alpha", "beta", proposal_beta.proposal_id,
        risks=["Latency spike under load"],
        missing_considerations=["No backpressure strategy"],
    )
    engine.submit_challenge(
        sid, "beta", "alpha", proposal_alpha.proposal_id,
        risks=["Operational complexity"],
        missing_considerations=["Missing retry semantics"],
    )

    # REVISION
    engine.submit_revision(
        sid, "alpha",
        accepted_feedback=["Latency spike under load"],
        rejected_feedback=["Operational complexity"],
        rejection_reasons=["Different proposal"],
        changed_design="Revised with circuit breaker",
    )
    engine.submit_revision(
        sid, "beta",
        accepted_feedback=["Missing retry semantics"],
        rejected_feedback=["Latency spike under load"],
        rejection_reasons=["Not applicable"],
        changed_design="Revised with bounded queue",
    )

    # OPTIMIZATION
    engine.submit_optimization(sid, "alpha", description="Batch processing")
    engine.submit_optimization(sid, "beta", description="Connection pooling")

    # DEVILS_ADVOCATE
    session = engine.store.get_session(sid)
    da_agent = session.devils_advocate_agent
    engine.submit_devils_advocate(
        sid, da_agent,
        failure_modes=["Memory exhaustion under burst"],
        risk_score=0.7,
    )

    # CONSENSUS
    engine.cast_consensus_vote(sid, "alpha", VoteType.AGREE, "Solid design")
    engine.cast_consensus_vote(sid, "beta", VoteType.AGREE, "Looks good")

    session = engine.store.get_session(sid)
    assert session.status == SessionStatus.COMPLETED
    return session


class TestReplayDeterminismFullDebateLifecycle:
    """场景 1：完整 debate lifecycle 的 replay 确定性。"""

    def test_full_lifecycle_replay_matches_original(self, engine):
        """完整辩论生命周期后，replay 结果与原始派生状态一致。"""
        session = _build_full_debate_session(engine)
        original = _snapshot_derived(session)

        # Corrupt + replay
        session.current_phase = DebatePhase.CREATED
        session.current_round = 0
        session.status = SessionStatus.CREATED
        result = _run_replay(engine, session)

        assert result["current_phase"] == original["current_phase"]
        assert result["current_round"] == original["current_round"]
        assert result["status"] == original["status"]
        assert result["clarify_refine_submitted"] == original["clarify_refine_submitted"]
        assert len(session.events) == len(_build_full_debate_session(engine).events)

    def test_full_lifecycle_replay_is_bit_identical(self, engine):
        """对同一事件流 replay 两次，输出结果完全一致。"""
        session = _build_full_debate_session(engine)
        _assert_replay_determinism(engine, session)


class TestReplayDeterminismHumanReview:
    """场景 2：多轮 human review 分支后的 replay 确定性。"""

    def _setup_human_review_session(self, engine):
        session = engine.create_session(
            title="Replay Human Review", description="Test"
        )
        sid = session.session_id
        engine.submit_requirement(sid, problem_statement="Build a system")
        engine.register_agent(sid, name="Agent1")
        engine.register_agent(sid, name="Agent2")

        # 模拟进入 human review：添加记录状态转换的 system event
        session = engine.store.get_session(sid)
        engine._add_event(
            session, EventType.SYSTEM_EVENT, "system",
            content="moved to human review"
        )
        session.status = SessionStatus.HUMAN_REVIEW
        engine.store.update_session(session)
        return session

    def test_human_review_replay_matches_original(self, engine):
        """human review 状态下 replay 结果一致。"""
        session = self._setup_human_review_session(engine)
        original = _snapshot_derived(session)

        session.current_phase = DebatePhase.CREATED
        session.current_round = 0
        session.status = SessionStatus.CREATED
        result = _run_replay(engine, session)

        assert result["status"] == original["status"]
        assert result["current_phase"] == original["current_phase"]

    def test_human_review_replay_is_bit_identical(self, engine):
        """human review 事件流 replay 两次结果一致。"""
        session = self._setup_human_review_session(engine)
        _assert_replay_determinism(engine, session)

    def test_post_human_vote_replay_matches_original(self, engine):
        """人类投票后 session 的 replay 结果一致。"""
        session = self._setup_human_review_session(engine)
        sid = session.session_id

        engine.submit_human_vote(sid, "Reviewer1", "agree", "Looks good")
        engine.submit_human_vote(sid, "Reviewer2", "agree", "Approved")

        session = engine.store.get_session(sid)
        assert session.status == SessionStatus.COMPLETED
        original = _snapshot_derived(session)

        session.current_phase = DebatePhase.CREATED
        session.current_round = 0
        session.status = SessionStatus.CREATED
        result = _run_replay(engine, session)

        assert result["status"] == original["status"]
        assert result["current_phase"] == original["current_phase"]


class TestReplayDeterminismWithUndo:
    """场景 3：带 undo（revert）后的 replay 确定性。"""

    def test_post_revert_replay_matches_original(self, engine):
        """revert 后 session 的 replay 结果与 revert 后的原始状态一致。"""
        session = engine.create_session(
            title="Replay Undo", description="Test"
        )
        sid = session.session_id
        engine.register_agent(sid, name="Alpha")
        engine.register_agent(sid, name="Beta")

        engine.submit_requirement(sid, problem_statement="Test undo")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)

        engine.submit_proposal(sid, "alpha", architecture="A")
        engine.submit_proposal(sid, "beta", architecture="B")

        # 记录一个 revert 目标点（在第一个 proposal 之前）
        session = engine.store.get_session(sid)
        proposal_phase_events = [e for e in session.events if e.phase == DebatePhase.PROPOSAL]
        target_event = proposal_phase_events[0]  # 第一个 PROPOSAL event

        # 继续推进到 CRITIC
        session = engine.store.get_session(sid)
        assert session.current_phase == DebatePhase.CRITIC

        # Revert 到 PROPOSAL 阶段的第一个 event
        engine.revert_to_event(sid, target_event.event_id)
        session = engine.store.get_session(sid)
        assert session.current_phase == DebatePhase.PROPOSAL

        original = _snapshot_derived(session)
        session.current_phase = DebatePhase.CREATED
        session.current_round = 0
        session.status = SessionStatus.CREATED
        result = _run_replay(engine, session)

        assert result["current_phase"] == original["current_phase"]
        assert result["current_round"] == original["current_round"]
        assert result["status"] == original["status"]

    def test_post_revert_replay_is_bit_identical(self, engine):
        """revert 后事件流 replay 两次结果一致。"""
        session = engine.create_session(
            title="Replay Undo Bit Identical", description="Test"
        )
        sid = session.session_id
        engine.register_agent(sid, name="Alpha")
        engine.register_agent(sid, name="Beta")

        engine.submit_requirement(sid, problem_statement="Test undo")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)
        engine.submit_proposal(sid, "alpha", architecture="A")
        engine.submit_proposal(sid, "beta", architecture="B")

        session = engine.store.get_session(sid)
        proposal_phase_events = [e for e in session.events if e.phase == DebatePhase.PROPOSAL]
        target_event = proposal_phase_events[0]

        engine.revert_to_event(sid, target_event.event_id)
        session = engine.store.get_session(sid)
        _assert_replay_determinism(engine, session)

    def test_multiple_reverts_replay_matches_original(self, engine):
        """多次 revert 后 replay 结果仍然一致。"""
        session = engine.create_session(
            title="Replay Multiple Undos", description="Test"
        )
        sid = session.session_id
        engine.register_agent(sid, name="Alpha")
        engine.register_agent(sid, name="Beta")

        engine.submit_requirement(sid, problem_statement="Test multi undo")
        engine.start_clarification(sid)
        engine.force_skip_clarification(sid)

        engine.submit_proposal(sid, "alpha", architecture="A")
        engine.submit_proposal(sid, "beta", architecture="B")

        # 第一次 revert：回退到第一个 proposal
        session = engine.store.get_session(sid)
        proposal_phase_events = [e for e in session.events if e.phase == DebatePhase.PROPOSAL]
        target1 = proposal_phase_events[0]
        engine.revert_to_event(sid, target1.event_id)

        # 再 submit 一次 proposal（产生新的事件流）
        engine.submit_proposal(sid, "alpha", architecture="Revised A")
        engine.submit_proposal(sid, "beta", architecture="Revised B")

        # 第二次 revert
        session = engine.store.get_session(sid)
        proposal_phase_events = [e for e in session.events if e.phase == DebatePhase.PROPOSAL]
        target2 = proposal_phase_events[-1]
        engine.revert_to_event(sid, target2.event_id)

        session = engine.store.get_session(sid)
        original = _snapshot_derived(session)
        session.current_phase = DebatePhase.CREATED
        session.current_round = 0
        session.status = SessionStatus.CREATED
        result = _run_replay(engine, session)

        assert result["current_phase"] == original["current_phase"]
        assert result["current_round"] == original["current_round"]
        assert result["status"] == original["status"]
