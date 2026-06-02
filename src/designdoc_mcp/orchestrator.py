from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
from dataclasses import dataclass, field
from typing import Any

from .engine import CollaborationEngine
from .models import (
    AgentInfo,
    DebatePhase,
    Session,
    SessionStatus,
    VoteType,
)

logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for an external agent process."""

    agent_id: str
    name: str
    # Command template must contain the literal substring {prompt}.
    # Example: 'claude -p {prompt}'
    # Example (Windows Cursor): 'powershell -Command "agent -p \'{prompt}\' --yolo"'
    command_template: str
    cwd: str | None = None
    env: dict[str, str] = field(default_factory=dict)
    timeout_seconds: int = 300
    max_retries: int = 2


class AgentExecutor:
    """Spawn an external agent process, feed it a prompt, and capture stdout."""

    def __init__(self, config: AgentConfig):
        self.config = config

    async def execute(self, prompt: str) -> str:
        """Run the agent command with *prompt* substituted in.

        Retries on non-zero exit or timeout with exponential backoff.
        """
        if "{prompt}" not in self.config.command_template:
            raise ValueError(
                f"Agent {self.config.agent_id} command_template missing {{prompt}} placeholder"
            )

        # Escape the prompt safely for shell substitution.
        # We use shlex.quote on Unix; on Windows the user is expected to have
        # crafted a PowerShell-safe template, so we only quote if the template
        # does not already contain explicit quoting.
        safe_prompt = self._escape_prompt(prompt)
        command = self.config.command_template.replace("{prompt}", safe_prompt)

        env = {**os.environ, **self.config.env}

        for attempt in range(self.config.max_retries + 1):
            proc: asyncio.subprocess.Process | None = None
            try:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.config.cwd,
                    env=env,
                )
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=self.config.timeout_seconds
                )
                stdout = stdout_b.decode("utf-8", errors="replace")
                stderr = stderr_b.decode("utf-8", errors="replace")

                if proc.returncode != 0:
                    raise RuntimeError(
                        f"Agent {self.config.agent_id} exited {proc.returncode}: {stderr[:500]}"
                    )
                return stdout

            except asyncio.TimeoutError:
                logger.warning(
                    "Agent %s timed out (attempt %d/%d)",
                    self.config.agent_id,
                    attempt + 1,
                    self.config.max_retries + 1,
                )
                if proc is not None and proc.returncode is None:
                    try:
                        proc.kill()
                        await proc.wait()
                    except Exception:
                        pass
                if attempt == self.config.max_retries:
                    raise RuntimeError(
                        f"Agent {self.config.agent_id} timed out after {self.config.max_retries + 1} attempts"
                    )

            except Exception as exc:
                logger.warning(
                    "Agent %s failed (attempt %d/%d): %s",
                    self.config.agent_id,
                    attempt + 1,
                    self.config.max_retries + 1,
                    exc,
                )
                if attempt == self.config.max_retries:
                    raise

            wait_sec = 2 ** attempt
            logger.info("Retrying agent %s in %ds...", self.config.agent_id, wait_sec)
            await asyncio.sleep(wait_sec)

        return ""

    def _escape_prompt(self, prompt: str) -> str:
        # If the template already wraps the placeholder in quotes, don't double-quote.
        template = self.config.command_template
        if f'"{prompt}"' in template or f"'{prompt}'" in template:
            return prompt
        # Simple heuristic: if the template looks like it will be passed to a shell,
        # quote the prompt to prevent injection.
        return shlex.quote(prompt)


class PromptBuilder:
    """Construct prompts for each debate phase."""

    @staticmethod
    def build(session: Session, agent: AgentInfo, phase: DebatePhase, context: dict) -> str:
        lines: list[str] = [
            "You are an AI agent participating in a structured design-document debate.",
            "",
            f"Session ID: {session.session_id}",
            f"Phase: {phase.value}",
            f"Round: {session.current_round}",
            f"Your Agent ID: {agent.agent_id}",
            f"Your Name: {agent.name}",
        ]
        if agent.current_perspective:
            lines.append(f"Your Perspective: {agent.current_perspective}")
            desc = context.get("perspective_description", "")
            if desc:
                lines.append(f"Perspective Description: {desc}")
        lines.append("")
        lines.append("=== CONTEXT ===")
        lines.append(json.dumps(context, indent=2, ensure_ascii=False))
        lines.append("")
        lines.append("=== YOUR TASK ===")
        lines.append(PromptBuilder._phase_instruction(phase, context))
        lines.append("")
        lines.append("=== RESPONSE FORMAT ===")
        lines.append("Respond ONLY with a single JSON object. Do not wrap it in markdown code fences.")
        lines.append("Do not include any explanatory text outside the JSON.")
        lines.append("")
        lines.append(PromptBuilder._phase_schema(phase, context))
        return "\n".join(lines)

    @staticmethod
    def _phase_instruction(phase: DebatePhase, context: dict) -> str:
        mapping: dict[DebatePhase, str] = {
            DebatePhase.CLARIFY_IDENTIFY: (
                "Identify assumptions in the requirement across all dimensions. "
                "For each assumption, provide alternatives for the human to choose from."
            ),
            DebatePhase.CLARIFY_REFINE: (
                "Supplement additional alternatives to existing assumptions. "
                "You may NOT remove or challenge assumptions raised by others."
            ),
            DebatePhase.CLARIFY_REWRITE: (
                "Propose a refined requirement document based on the merged assumptions and human choices."
            ),
            DebatePhase.PROPOSAL: (
                "Propose a solution architecture from your assigned perspective. "
                "You MUST NOT read other agents' proposals (they are hidden to avoid anchoring bias)."
            ),
            DebatePhase.CRITIC: (
                "Challenge another agent's proposal. You MUST:\n"
                "1. Identify at least 3 risks, 2 missing considerations, and 1 alternative.\n"
                "2. Choose a specific proposal to challenge (provide its target_agent_id and target_proposal_id).\n"
                "Vague agreement like 'I agree' is FORBIDDEN."
            ),
            DebatePhase.REVISION: (
                "Revise your proposal by incorporating valid feedback.\n"
                "Explicitly state which feedback you accept or reject with reasons.\n"
                "Polite acknowledgment without design changes is FORBIDDEN."
            ),
            DebatePhase.OPTIMIZATION: (
                "Propose an optimization to the current design: simpler, more stable, cheaper, "
                "more maintainable, or more scalable alternative."
            ),
            DebatePhase.DEVILS_ADVOCATE: (
                "You are the Devil's Advocate. Assume the current design WILL FAIL.\n"
                "Prove why by listing concrete failure modes, risk scores, and mitigations."
            ),
            DebatePhase.CONSENSUS: (
                "Cast your final vote on the refined design.\n"
                "Options: agree, disagree, abstain, needs_clarification."
            ),
        }
        return mapping.get(phase, "Follow the context and return the required JSON.")

    @staticmethod
    def _phase_schema(phase: DebatePhase, context: dict) -> str:
        schemas: dict[DebatePhase, str] = {
            DebatePhase.CLARIFY_IDENTIFY: (
                '{"assumptions": [{"dimension": "string", "assumption": "string", '
                '"confidence": 0.5, "alternatives": [{"label": "string", "description": "string"}], '
                '"rationale": "string"}]}'
            ),
            DebatePhase.CLARIFY_REFINE: (
                '{"supplements": [{"assumption_id": "string", "label": "string", "description": "string"}]}'
            ),
            DebatePhase.CLARIFY_REWRITE: (
                '{"refined_statement": "string", "constraints": ["string"], '
                '"acceptance_criteria": ["string"]}'
            ),
            DebatePhase.PROPOSAL: (
                '{"architecture": "string (required)", "tech_stack": "string", '
                '"tradeoffs": "string", "risks": "string", "assumptions": "string", '
                '"unknowns": "string"}'
            ),
            DebatePhase.CRITIC: (
                '{"target_agent_id": "string", "target_proposal_id": "string", '
                '"risks": ["string"], "missing_considerations": ["string"], '
                '"alternative_proposal": "string"}'
            ),
            DebatePhase.REVISION: (
                '{"accepted_feedback": ["string"], "rejected_feedback": ["string"], '
                '"rejection_reasons": ["string"], "changed_design": "string"}'
            ),
            DebatePhase.OPTIMIZATION: (
                '{"description": "string (required)", "impact": "string", '
                '"tradeoff": "string", "complexity_change": "string"}'
            ),
            DebatePhase.DEVILS_ADVOCATE: (
                '{"failure_modes": ["string (required)"], "risk_score": 0.0, "mitigation": "string"}'
            ),
            DebatePhase.CONSENSUS: (
                '{"vote_type": "agree|disagree|abstain|needs_clarification", "comment": "string"}'
            ),
        }
        return schemas.get(phase, "Return a JSON object matching the expected schema.")


class ResultParser:
    """Extract JSON from agent stdout and map to engine submit parameters."""

    @staticmethod
    def extract_json(stdout: str) -> dict:
        stdout = stdout.strip()
        if not stdout:
            raise ValueError("Agent returned empty stdout")

        # Strip markdown code fences if present
        if stdout.startswith("```"):
            match = re.search(r"```(?:json)?\s*(.*?)```", stdout, re.DOTALL)
            if match:
                stdout = match.group(1).strip()
            else:
                # Handle opening fence without closing
                stdout = stdout.removeprefix("```json").removeprefix("```").strip()

        try:
            return json.loads(stdout)
        except json.JSONDecodeError as exc:
            # Try to find the first JSON object in the text
            match = re.search(r"\{.*\}", stdout, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    pass
            raise ValueError(f"Failed to parse JSON from agent output: {exc}") from exc

    @staticmethod
    def parse_clarify_identify(data: dict) -> dict:
        return {"assumptions": data.get("assumptions", [])}

    @staticmethod
    def parse_clarify_refine(data: dict) -> dict:
        return {"supplements": data.get("supplements", [])}

    @staticmethod
    def parse_clarify_rewrite(data: dict) -> dict:
        return {
            "refined_statement": data.get("refined_statement", ""),
            "constraints": data.get("constraints", []),
            "acceptance_criteria": data.get("acceptance_criteria", []),
        }

    @staticmethod
    def parse_proposal(data: dict) -> dict:
        return {
            "architecture": data.get("architecture", ""),
            "tech_stack": data.get("tech_stack", ""),
            "tradeoffs": data.get("tradeoffs", ""),
            "risks": data.get("risks", ""),
            "assumptions": data.get("assumptions", ""),
            "unknowns": data.get("unknowns", ""),
            "raw_content": json.dumps(data),
        }

    @staticmethod
    def parse_challenge(data: dict, session: Session, agent_id: str) -> dict:
        """Parse challenge data and auto-correct invalid targets."""
        target_agent_id = data.get("target_agent_id", "")
        target_proposal_id = data.get("target_proposal_id", "")

        # Build valid targets
        current_round = session.current_round
        proposals = [p for p in session.proposals if p.round_number == current_round]
        valid_targets = {p.agent_id: p.proposal_id for p in proposals}

        active_count = sum(1 for a in session.agents if a.is_active)

        # Cannot target self in multi-agent mode
        if target_agent_id == agent_id and active_count > 1:
            # Pick first non-self target
            for aid, pid in valid_targets.items():
                if aid != agent_id:
                    target_agent_id = aid
                    target_proposal_id = pid
                    break

        # Validate target exists
        if target_agent_id not in valid_targets:
            # Fallback to first available
            for aid, pid in valid_targets.items():
                if aid != agent_id or active_count == 1:
                    target_agent_id = aid
                    target_proposal_id = pid
                    break

        # Ensure proposal_id matches agent
        if valid_targets.get(target_agent_id) != target_proposal_id:
            target_proposal_id = valid_targets.get(target_agent_id, target_proposal_id)

        return {
            "target_agent_id": target_agent_id,
            "target_proposal_id": target_proposal_id,
            "risks": data.get("risks", []),
            "missing_considerations": data.get("missing_considerations", []),
            "alternative_proposal": data.get("alternative_proposal", ""),
        }

    @staticmethod
    def parse_revision(data: dict) -> dict:
        return {
            "accepted_feedback": data.get("accepted_feedback", []),
            "rejected_feedback": data.get("rejected_feedback", []),
            "rejection_reasons": data.get("rejection_reasons", []),
            "changed_design": data.get("changed_design", ""),
        }

    @staticmethod
    def parse_optimization(data: dict) -> dict:
        return {
            "description": data.get("description", ""),
            "impact": data.get("impact", ""),
            "tradeoff": data.get("tradeoff", ""),
            "complexity_change": data.get("complexity_change", ""),
        }

    @staticmethod
    def parse_devils_advocate(data: dict) -> dict:
        return {
            "failure_modes": data.get("failure_modes", []),
            "risk_score": float(data.get("risk_score", 0.5)),
            "mitigation": data.get("mitigation", ""),
        }

    @staticmethod
    def parse_consensus(data: dict) -> dict:
        raw = data.get("vote_type", "abstain")
        try:
            vote_type = VoteType(raw)
        except ValueError:
            vote_type = VoteType.ABSTAIN
        return {
            "vote_type": vote_type,
            "comment": data.get("comment", ""),
        }


class Orchestrator:
    """Drive a debate session by spawning external agent processes per phase."""

    def __init__(self, engine: CollaborationEngine, agent_configs: list[AgentConfig]):
        self.engine = engine
        self.agent_configs: dict[str, AgentConfig] = {c.agent_id: c for c in agent_configs}
        self._shutdown = False

    def shutdown(self) -> None:
        self._shutdown = True

    async def run_session(self, session_id: str, poll_interval: float = 2.0) -> None:
        """Drive *session_id* until it reaches COMPLETED, HUMAN_REVIEW, or ARCHIVED."""
        logger.info("Orchestrator starting session %s", session_id)

        while not self._shutdown:
            session = self.engine.store.get_session(session_id)
            if session is None:
                raise ValueError(f"Session {session_id} not found")

            if session.status in (SessionStatus.COMPLETED, SessionStatus.ARCHIVED):
                logger.info("Session %s finished (%s)", session_id, session.status.value)
                break

            if session.status == SessionStatus.HUMAN_REVIEW:
                logger.info("Session %s entered HUMAN_REVIEW. Pausing.", session_id)
                # Future: emit notification / WebSocket event here
                break

            phase = session.current_phase

            # Wait phases that require external human action
            if phase in (DebatePhase.CREATED, DebatePhase.CLARIFY_REVIEW):
                logger.debug("Session %s in wait phase %s", session_id, phase.value)
                await asyncio.sleep(poll_interval)
                continue

            agents_to_run = self._agents_for_phase(session)
            if not agents_to_run:
                await asyncio.sleep(poll_interval)
                continue

            pending = self._pending_agents(session, agents_to_run)
            if not pending:
                # Everyone has submitted; engine should auto-advance shortly
                await asyncio.sleep(0.5)
                continue

            # Execute pending agents concurrently
            tasks = [self._execute_agent(session, agent_id) for agent_id in pending]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for agent_id, result in zip(pending, results):
                if isinstance(result, Exception):
                    logger.error(
                        "Agent %s failed in %s: %s", agent_id, phase.value, result
                    )
                else:
                    logger.info("Agent %s completed %s", agent_id, phase.value)

            # Brief pause to let engine persist state before next iteration
            await asyncio.sleep(0.5)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _agents_for_phase(self, session: Session) -> list[str]:
        """Return agent IDs that should act in the current phase."""
        if session.status in (
            SessionStatus.COMPLETED,
            SessionStatus.HUMAN_REVIEW,
            SessionStatus.ARCHIVED,
        ):
            return []

        phase = session.current_phase
        if phase == DebatePhase.DEVILS_ADVOCATE:
            if session.devils_advocate_agent:
                return [session.devils_advocate_agent]
            return []

        # All other active phases: every active agent
        return [a.agent_id for a in session.agents if a.is_active]

    def _pending_agents(self, session: Session, agent_ids: list[str]) -> list[str]:
        """Return subset of *agent_ids* that have not yet submitted for current phase."""
        phase = session.current_phase
        submitted: set[str] = set()

        if phase == DebatePhase.CLARIFY_IDENTIFY:
            submitted = {
                a.agent_id
                for a in session.assumptions
                if a.clarify_round == session.clarify_round
            }
        elif phase == DebatePhase.CLARIFY_REFINE:
            submitted = set(session.clarify_refine_submitted)
        elif phase == DebatePhase.CLARIFY_REWRITE:
            submitted = {r.agent_id for r in session.refined_requirements}
        elif phase == DebatePhase.PROPOSAL:
            submitted = {
                p.agent_id for p in session.proposals if p.round_number == session.current_round
            }
        elif phase == DebatePhase.CRITIC:
            submitted = {
                c.agent_id for c in session.challenges if c.round_number == session.current_round
            }
        elif phase == DebatePhase.REVISION:
            submitted = {
                r.agent_id for r in session.revisions if r.round_number == session.current_round
            }
        elif phase == DebatePhase.OPTIMIZATION:
            submitted = {
                o.agent_id
                for o in session.optimizations
                if o.round_number == session.current_round
            }
        elif phase == DebatePhase.DEVILS_ADVOCATE:
            submitted = {
                d.agent_id
                for d in session.devils_advocates
                if d.round_number == session.current_round
            }
        elif phase == DebatePhase.CONSENSUS:
            submitted = {
                v.agent_id for v in session.consensus_votes if v.round_number == session.current_round
            }

        return [aid for aid in agent_ids if aid not in submitted]

    async def _execute_agent(self, session: Session, agent_id: str) -> None:
        """Spawn one agent, parse its output, and submit to the engine."""
        config = self.agent_configs.get(agent_id)
        if config is None:
            raise ValueError(f"No AgentConfig registered for agent_id={agent_id}")

        agent = next((a for a in session.agents if a.agent_id == agent_id), None)
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found in session {session.session_id}")

        phase = session.current_phase
        context = self.engine.get_phase_context(session.session_id, agent_id)
        prompt = PromptBuilder.build(session, agent, phase, context)

        executor = AgentExecutor(config)
        stdout = await executor.execute(prompt)

        data = ResultParser.extract_json(stdout)
        self._submit(session, agent_id, phase, data)

    def _submit(
        self, session: Session, agent_id: str, phase: DebatePhase, data: dict
    ) -> None:
        """Dispatch to the correct engine submit method."""
        sid = session.session_id

        if phase == DebatePhase.CLARIFY_IDENTIFY:
            kwargs = ResultParser.parse_clarify_identify(data)
            self.engine.submit_assumptions(sid, agent_id, **kwargs)

        elif phase == DebatePhase.CLARIFY_REFINE:
            kwargs = ResultParser.parse_clarify_refine(data)
            self.engine.supplement_assumption_options(sid, agent_id, **kwargs)

        elif phase == DebatePhase.CLARIFY_REWRITE:
            kwargs = ResultParser.parse_clarify_rewrite(data)
            self.engine.submit_refined_requirement(sid, agent_id, **kwargs)

        elif phase == DebatePhase.PROPOSAL:
            kwargs = ResultParser.parse_proposal(data)
            self.engine.submit_proposal(sid, agent_id, **kwargs)

        elif phase == DebatePhase.CRITIC:
            kwargs = ResultParser.parse_challenge(data, session, agent_id)
            self.engine.submit_challenge(sid, agent_id, **kwargs)

        elif phase == DebatePhase.REVISION:
            kwargs = ResultParser.parse_revision(data)
            self.engine.submit_revision(sid, agent_id, **kwargs)

        elif phase == DebatePhase.OPTIMIZATION:
            kwargs = ResultParser.parse_optimization(data)
            self.engine.submit_optimization(sid, agent_id, **kwargs)

        elif phase == DebatePhase.DEVILS_ADVOCATE:
            kwargs = ResultParser.parse_devils_advocate(data)
            self.engine.submit_devils_advocate(sid, agent_id, **kwargs)

        elif phase == DebatePhase.CONSENSUS:
            kwargs = ResultParser.parse_consensus(data)
            self.engine.cast_consensus_vote(sid, agent_id, **kwargs)

        else:
            logger.warning("Orchestrator does not know how to submit for phase %s", phase.value)
