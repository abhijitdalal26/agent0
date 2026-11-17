from __future__ import annotations

import time
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.usage import UsageLimits

from agent0.agents.definitions import AgentDef
from agent0.core.types import Artifact, Capability, EventType, RunStatus, Task, utcnow
from agent0.knowledge.base import SourceRecord
from agent0.memory.base import RunSummary
from agent0.memory.extract import build_extraction_agent, extract_and_apply
from agent0.models.base import ModelProfile, NoProfileAvailable
from agent0.models.chat import build_fallback, build_model
from agent0.models.usage import Units, UsageMeter, compute_cost, record_from_run_usage
from agent0.orchestrator.runtime import Runtime
from agent0.orchestrator.tools import RunDeps, knowledge_toolset, media_toolset, summarize_args
from agent0.policy.budget import BudgetExceeded, BudgetMeter
from agent0.policy.permissions import ApprovalRequired, Decision, Policy
from agent0.tools import build_toolset
from agent0.tools.deps import call_key
from agent0.verify import (
    JudgeModel,
    TaskSpec,
    Verdict,
    VerdictStatus,
    Verifier,
    VerifyContext,
    default_registry,
)
from agent0.verify.base import CheckType


class PendingApproval(BaseModel):
    tool: str
    args: dict[str, Any]
    reason: str
    key: str


class AttemptResult(BaseModel):
    status: Literal["done", "needs_approval", "budget", "error"]
    output: str = ""
    provider: str | None = None
    profile: str | None = None
    sources: list[SourceRecord] = Field(default_factory=list)
    artifacts: list[str] = Field(default_factory=list)
    approval: PendingApproval | None = None
    cost_usd: float = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    error: str | None = None


class Report(BaseModel):
    passed: bool
    verdicts: list[Verdict]
    feedback: str = ""
    cost_usd: float = 0.0
    awaiting_approval: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def _profiles(rt: Runtime, prefer: str, exclude_provider: str | None = None) -> list[ModelProfile]:
    ranked = rt.router.rank(Capability.CHAT, prefer=prefer, exclude_provider=exclude_provider)  # type: ignore[arg-type]
    return [r.profile for r in ranked[:2]]


def _policy(agent: AgentDef, rt: Runtime) -> Policy:
    roots = (
        ("/workspace",) if rt.settings.sandbox == "docker" else (str(rt.settings.workspace_root.resolve()),)
    )
    tools = {k: Decision(v) for k, v in agent.policy.get("tools", {}).items()}
    return Policy(tools=tools, workspace_roots=roots)


class Engine:
    """The steps of one task run. Each method is also a Temporal activity body, so inputs/outputs are data."""

    def __init__(self, rt: Runtime) -> None:
        self.rt = rt

    async def _record_chat(self, run_id: str, profile: ModelProfile, usage: Any, ms: int, ok: bool) -> float:
        record = record_from_run_usage(profile, usage, run_id=run_id, latency_ms=ms, ok=ok)
        await self.rt.usage.record(record)
        await self.rt.events.emit(
            run_id,
            EventType.MODEL_CALL,
            {
                "profile": profile.name,
                "provider": profile.provider,
                "model": profile.model,
                "tokens_in": record.input_units,
                "tokens_out": record.output_units,
                "cost_usd": record.cost_usd,
                "latency_ms": ms,
            },
        )
        if self.rt.repos:
            await self.rt.repos.runs.add_usage(
                run_id, record.input_units, record.output_units, record.cost_usd
            )
        return record.cost_usd

    async def set_status(self, task: Task, run_id: str, status: RunStatus, step: str | None = None) -> None:
        if self.rt.repos:
            fields: dict[str, Any] = {"status": status.value, "current_step": step}
            if status in (RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.STOPPED):
                fields["ended_at"] = utcnow()
            await self.rt.repos.runs.update(run_id, **fields)
            await self.rt.repos.tasks.set_status(task.id, status.value)

    async def plan(self, task: Task, run_id: str) -> TaskSpec:
        await self.rt.events.emit(run_id, EventType.RUN_STARTED, {"task_id": task.id, "title": task.title})
        planner = self.rt.agents.get("planner")
        profiles = _profiles(self.rt, planner.prefer or "smart")
        recall = await self.rt.memory.recall(task.prompt)
        if recall.facts or recall.past_runs:
            await self.rt.events.emit(
                run_id,
                EventType.MEMORY_RECALLED,
                {"facts": len(recall.facts), "past_runs": len(recall.past_runs)},
            )
        prompt = f"<task>\n{task.prompt}\n</task>"
        if memory := recall.render():
            prompt += f"\n\n<memory>\n{memory}\n</memory>"
        if tools := self._tool_names():
            prompt += f"\n\nThe executor can use these tools: {', '.join(tools)}."
        agent = Agent(build_fallback(profiles), output_type=TaskSpec, instructions=planner.instructions)
        started = time.monotonic()
        result = await agent.run(prompt)
        await self._record_chat(
            run_id, profiles[0], result.usage(), int((time.monotonic() - started) * 1000), True
        )
        spec = result.output
        if self.rt.repos:
            await self.rt.repos.task_specs.upsert(task.id, spec)
        await self.rt.events.emit(run_id, EventType.PLAN_CREATED, spec.model_dump(mode="json"))
        return spec

    def _tool_names(self) -> list[str]:
        names = ["shell", "read_file", "write_file", "list_files", "web_fetch"]
        if self.rt.knowledge:
            names += ["list_sources", "search_knowledge", "query_sql"]
        available = {p.capability for p in self.rt.registry.available()}
        if Capability.IMAGE_GEN in available:
            names.append("generate_image")
        if Capability.TTS in available:
            names.append("text_to_speech")
        if Capability.STT in available:
            names.append("transcribe_audio")
        return names

    def _executor_prompt(self, task: Task, spec: TaskSpec, feedback: str | None, recall: str) -> str:
        criteria = "\n".join(f"- [{c.type}] {c.description}" for c in spec.criteria)
        steps = "\n".join(f"{i}. {s}" for i, s in enumerate(spec.steps, 1))
        parts = [
            f"<task>\n{task.prompt}\n</task>",
            f"Goal: {spec.goal}\n\nPlan:\n{steps}\n\nYour work will be checked against:\n{criteria}",
        ]
        if recall:
            parts.append(f"<memory>\n{recall}\n</memory>")
        if skills := self.rt.skills.index():
            parts.append(f"Skills you can load with load_skill(name) when relevant:\n{skills}")
        if feedback:
            parts.append(
                f"<previous_attempt_failed>\n{feedback}\n</previous_attempt_failed>\nFix these problems."
            )
        parts.append("Finish with a short summary of what you produced and where (file paths).")
        return "\n\n".join(parts)

    async def execute(
        self, task: Task, spec: TaskSpec, run_id: str, attempt: int, feedback: str | None, approved: list[str]
    ) -> AttemptResult:
        from agent0.extensions.skills import skill_toolset

        agent_def = self.rt.agents.get(task.agent)
        budget = agent_def.effective_budget(task.budget)
        try:
            profiles = _profiles(self.rt, agent_def.prefer or "smart")
        except NoProfileAvailable as exc:
            return AttemptResult(status="error", error=str(exc))
        sandbox = await self.rt.sandboxes.create(run_id, self.rt.settings.sandbox_image)
        deps = RunDeps(
            run_id=run_id,
            sandbox=sandbox,
            events=self.rt.events,
            policy=_policy(agent_def, self.rt),
            budget=BudgetMeter(budget),
            approved=set(approved),
            knowledge=self.rt.knowledge,
            router=self.rt.router,
            meter=UsageMeter(self.rt.usage, run_id=run_id),
        )
        allowed_skills = None if agent_def.skills == "all" or not agent_def.skills else list(agent_def.skills)
        toolsets: list[Any] = [
            build_toolset(),
            media_toolset(),
            skill_toolset(self.rt.skills, self.rt.events, run_id, allowed_skills),
            *self.rt.mcp.toolsets(agent_def.mcp),
        ]
        if self.rt.knowledge:
            toolsets.append(knowledge_toolset())
        recall = (await self.rt.memory.recall(task.prompt)).render()
        agent = Agent(
            build_fallback(profiles),
            deps_type=RunDeps,
            instructions=agent_def.instructions,
            toolsets=toolsets,
        )
        started = time.monotonic()
        result: AttemptResult
        try:
            run = await agent.run(
                self._executor_prompt(task, spec, feedback, recall),
                deps=deps,
                usage_limits=UsageLimits(request_limit=budget.max_steps),
            )
            cost = await self._record_chat(run_id, profiles[0], run.usage(), self._ms(started), True)
            usage = run.usage()
            result = AttemptResult(
                status="done",
                output=run.output,
                provider=profiles[0].provider,
                profile=profiles[0].name,
                cost_usd=cost,
                tokens_in=usage.input_tokens,
                tokens_out=usage.output_tokens,
            )
        except ApprovalRequired as exc:
            key = call_key(exc.tool, exc.tool_args)
            result = AttemptResult(
                status="needs_approval",
                approval=PendingApproval(tool=exc.tool, args=exc.tool_args, reason=exc.reason, key=key),
            )
        except (BudgetExceeded, UsageLimitExceeded) as exc:
            await self.rt.events.emit(run_id, EventType.BUDGET_EXCEEDED, {"reason": str(exc)})
            result = AttemptResult(status="budget", error=str(exc))
        except Exception as exc:
            await self.rt.events.emit(run_id, EventType.ERROR, {"message": f"{type(exc).__name__}: {exc}"})
            result = AttemptResult(status="error", error=f"{type(exc).__name__}: {exc}")
        finally:
            await sandbox.destroy()
        result.sources = deps.sources
        result.artifacts = deps.artifacts
        result.provider = result.provider or profiles[0].provider
        return result

    @staticmethod
    def _ms(started: float) -> int:
        return int((time.monotonic() - started) * 1000)

    def _judge_factory(self, run_id: str):
        def factory(exclude_provider: str | None) -> JudgeModel:
            try:
                profile = self.rt.router.pick(
                    Capability.CHAT, prefer="smart", exclude_provider=exclude_provider
                )
            except NoProfileAvailable:
                # Single-provider setups still get a judge, just not an independent one.
                profile = self.rt.router.pick(Capability.CHAT, prefer="smart")

            def cost(usage: Any) -> float:
                return compute_cost(
                    profile, Units(input_tokens=usage.input_tokens, output_tokens=usage.output_tokens)
                )

            return JudgeModel(build_model(profile), profile.provider, cost)

        return factory

    async def verify(self, task: Task, spec: TaskSpec, run_id: str, attempt: AttemptResult) -> Report:
        factory = self._judge_factory(run_id)
        registry = default_registry(judge_factory=factory)
        for register in self.rt.check_registrars:
            register(registry)
        sandbox = await self.rt.sandboxes.create(run_id, self.rt.settings.sandbox_image)
        try:
            ctx = VerifyContext(
                run_id=run_id,
                task_prompt=task.prompt,
                output=attempt.output,
                sandbox=sandbox,
                sources=attempt.sources,
                executor_provider=attempt.provider,
            )
            report = await Verifier(registry, factory, self.rt.events).verify(spec, ctx)
        finally:
            await sandbox.destroy()
        if self.rt.repos:
            for verdict in report.verdicts:
                await self.rt.repos.verdicts.add(run_id, verdict)
        return Report(
            passed=report.passed,
            verdicts=report.verdicts,
            feedback=report.feedback,
            cost_usd=report.cost_usd,
            awaiting_approval=report.awaiting_approval,
            warnings=report.warnings,
        )

    async def create_approval(self, task: Task, run_id: str, question: str) -> str:
        approval_id = None
        if self.rt.repos:
            row = await self.rt.repos.approvals.create(run_id, question)
            approval_id = row["id"]
        else:
            from agent0.orchestrator.tools import approval_id as new_approval_id

            approval_id = new_approval_id()
        await self.rt.events.emit(
            run_id, EventType.APPROVAL_REQUESTED, {"approval_id": approval_id, "question": question}
        )
        await self.rt.notify_approval(task.chat_id, run_id, approval_id, question)
        return approval_id

    async def record_decision(self, run_id: str, approval_id: str, decision: str, by: str) -> None:
        await self.rt.events.emit(
            run_id, EventType.APPROVAL_DECIDED, {"approval_id": approval_id, "decision": decision, "by": by}
        )

    async def notify(self, task: Task, text: str, attachments: list[str] | None = None) -> None:
        await self.rt.notify(task.chat_id, text, attachments or [])

    async def finish(
        self,
        task: Task,
        run_id: str,
        status: RunStatus,
        attempt: AttemptResult | None,
        report: Report | None,
        attempts: int,
    ) -> str:
        await self.set_status(task, run_id, status)
        outcome = status.value
        failed = [v for v in (report.verdicts if report else []) if v.status != VerdictStatus.PASS]
        summary = f"Task: {task.title}. Outcome: {outcome} after {attempts} attempt(s)."
        if failed:
            summary += " Failed checks: " + "; ".join(
                f"{v.check_id} ({v.type}): {v.evidence[:160]}" for v in failed
            )
        if attempt and attempt.error:
            summary += f" Error: {attempt.error[:200]}"
        await self.rt.memory.save_run(RunSummary(run_id=run_id, summary=summary, outcome=outcome))
        await self._remember(run_id, summary)
        if self.rt.repos and attempt:
            for path in attempt.artifacts:
                await self.rt.repos.artifacts.add(Artifact(run_id=run_id, path=path, kind=_kind(path)))
        await self.rt.events.emit(
            run_id,
            EventType.RUN_FINISHED,
            {"status": outcome, "attempts": attempts, "cost_usd": (attempt.cost_usd if attempt else 0.0)},
        )
        return summary

    async def _remember(self, run_id: str, summary: str) -> None:
        try:
            profile = self.rt.router.pick(Capability.CHAT, prefer="cheap")
        except NoProfileAvailable:
            return
        agent = build_extraction_agent(build_model(profile))
        started = time.monotonic()
        try:
            applied = await extract_and_apply(self.rt.memory, summary, agent, run_id=run_id)
        except Exception as exc:
            await self.rt.events.emit(
                run_id, EventType.ERROR, {"message": f"memory extraction failed: {exc}"}
            )
            return
        await self.rt.events.emit(
            run_id,
            EventType.MEMORY_SAVED,
            {"items": [{"content": f.content, "verdict": v} for f, v, _ in applied], "ms": self._ms(started)},
        )


def _kind(path: str) -> str:
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return {
        "png": "image",
        "jpg": "image",
        "jpeg": "image",
        "webp": "image",
        "gif": "image",
        "wav": "audio",
        "mp3": "audio",
        "ogg": "audio",
        "md": "markdown",
        "json": "json",
        "pdf": "pdf",
        "mp4": "video",
        "txt": "text",
        "html": "text",
        "csv": "text",
    }.get(ext, "other")


def approval_question(pending: PendingApproval) -> str:
    return f"Allow `{pending.tool}`({summarize_args(pending.args)})? Reason: {pending.reason}"


def human_question(task: Task, attempt: AttemptResult, report: Report) -> str:
    files = ", ".join(attempt.artifacts) or "see output"
    asks = "; ".join(
        v.evidence.removeprefix("needs_approval:").strip()
        for v in report.verdicts
        if v.type == CheckType.HUMAN
    )
    return f"Review result of '{task.title}' ({files}). {asks}\n\n{attempt.output[:800]}"
