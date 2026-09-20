"""The production Agent[I, O] base — the central abstraction.

Every ClinCase agent (parent or sub-agent) is a subclass of `Agent[I, O]`.
The base class implements the full production lifecycle:

    invoke(input, ctx) →
      1. validate input schema
      2. run input guardrails       (PHI mask · token-budget · custom)
      3. reserve budget             (cost/token/latency ceilings)
      4. plan                       (optional; for multi-step / tool-using agents)
      5. act                        (LLM call OR pure-Python execute)
      6. validate output schema     (retry-with-feedback on parse failure)
      7. run output guardrails      (citation completeness · custom)
      8. reflect                    (optional Grader → retry if score below threshold)
      9. commit budget
     10. emit AgentTrace span and persist agent_runs row
     11. return AgentResult[O]

The same lifecycle works for LLM agents and deterministic agents — the only
difference is whether step 5 calls Bedrock or pure Python. This is what
unifies the framework.

Agents are STATELESS class instances; per-invocation state lives on the
AgentContext.WorkingMemory and the AgentTrace.
"""
from __future__ import annotations

import time
import uuid
from abc import ABC
from datetime import UTC, datetime
from typing import Any, ClassVar, Generic, TypeVar

from pydantic import BaseModel

from app.agents.framework import cache as response_cache
from app.agents.framework.budget import BudgetExceeded
from app.agents.framework.context import AgentContext
from app.agents.framework.grader import GraderInput, LLMGrader, get_default_grader
from app.agents.framework.guardrails import (
    Guardrail,
    GuardrailDecision,
)
from app.agents.framework.models import (
    ModelRouter,
    ModelSpec,
    estimate_cost,
    resolve_model_id,
)
from app.agents.framework.types import (
    AgentMetadata,
    AgentResult,
    AgentTrace,
    Cost,
    SpanKind,
    SpanStatus,
    TokenUsage,
)
from app.llm import LLMResponse, get_llm_client
from app.llm.gateway import (
    GatewayCallContext,
    reset_call_context,
    set_call_context,
)

I = TypeVar("I", bound=BaseModel)
O = TypeVar("O", bound=BaseModel)


def _strip_code_fence(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end = len(lines) - 1 if lines[-1].strip().startswith("```") else len(lines)
        text = "\n".join(lines[1:end])
    return text.strip()


# =============================================================================
# Agent[I, O]
# =============================================================================


class Agent(ABC, Generic[I, O]):
    """A first-class production agent.

    Subclass overrides:
      • Identity              — name, parent (or None for top-level), role, description
      • Schemas               — input_schema, output_schema
      • Models                — primary_model, fallback_model (optional)
      • Guardrails            — input_guardrails, output_guardrails
      • Reflection            — quality_threshold, max_iterations, grader (optional)
      • Implementation        — exactly ONE of:
                                  (a) `system_prompt` + `_build_user_message` → LLM agent
                                  (b) `_execute_deterministic` → pure-Python agent

    The base class handles the lifecycle in `invoke()` — subclasses do NOT
    override `invoke()` directly.
    """

    # --- Identity (required) ---
    name: ClassVar[str]
    parent: ClassVar[str | None] = None
    role: ClassVar[str] = ""
    description: ClassVar[str] = ""

    # --- Schemas (required) ---
    input_schema: ClassVar[type[BaseModel]]
    output_schema: ClassVar[type[BaseModel]]

    # --- Models ---
    primary_model: ClassVar[ModelSpec | None] = None
    """LLM agents declare this. Deterministic agents leave it None."""
    fallback_model: ClassVar[ModelSpec | None] = None
    """Stronger model for retry on failure. Defaults to ModelRouter.escalate(primary)."""

    # --- Guardrails ---
    input_guardrails: ClassVar[list[Guardrail]] = []
    output_guardrails: ClassVar[list[Guardrail]] = []

    # --- Reflection / self-correction ---
    quality_threshold: ClassVar[float] = 0.0
    """If > 0, the grader runs after each attempt. Below threshold → retry up to max_iterations."""
    max_iterations: ClassVar[int] = 1
    """Max attempts including the initial one. Bounded loop."""
    grader: ClassVar[LLMGrader | None] = None
    """Override to use a custom grader. Default: shared singleton on first quality check."""

    # --- Budget hints (for budget reservation) ---
    estimated_input_tokens: ClassVar[int] = 1000
    estimated_output_tokens: ClassVar[int] = 800

    # --- Prompt for LLM agents ---
    system_prompt: ClassVar[str] = ""

    # --- Deterministic response cache (SCALE-9) ---
    # Default ON for LLM agents. Two reasons agents would opt out:
    #   • The agent intentionally non-determines (e.g. random patient framings).
    #   • The output is consumed for time-sensitive analytics where stale = wrong.
    # Most extractive / matching / classification agents are good cache citizens.
    cache_enabled: ClassVar[bool] = True
    cache_ttl_seconds: ClassVar[int] = 60 * 60   # 1 hour default per-row TTL

    # --- Per-agent performance budget (industry-grade scale-up) ---
    # Per-agent p95 latency budget in milliseconds. Breaches surface as
    # span events + Prometheus counter (clincase_agent_perf_budget_breach_total)
    # so HPA + alerting can react. Default 30s — most agents finish in <10s;
    # reflection-enabled agents can take longer.
    p95_latency_budget_ms: ClassVar[int] = 30_000

    # ------------------------------------------------------------------
    # Abstract hooks — subclasses implement ONE of these two
    # ------------------------------------------------------------------

    def _build_user_message(self, input: I) -> str:
        """LLM agents: render input as the user message. Default is JSON dump."""
        return input.model_dump_json(indent=2)

    async def _execute_deterministic(self, input: I, ctx: AgentContext) -> O:
        """Deterministic agents override this. LLM agents leave it raising."""
        raise NotImplementedError(
            "_execute_deterministic must be overridden by deterministic agents."
        )

    def _execute(self, input: I) -> O:
        """Synchronous test helper for deterministic agents.

        Runs `_execute_deterministic` in an isolated event loop and restores
        the prior event-loop policy so we don't disturb pytest-asyncio's
        session-scoped loop in the test suite.

        ONLY valid on deterministic agents whose body doesn't reference `ctx`.
        """
        if self.primary_model is not None:
            raise RuntimeError(
                f"{type(self).__name__}._execute is only available on "
                f"deterministic agents (primary_model is None)."
            )
        import asyncio

        # Refuse if we're already inside a running event loop
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            pass
        else:
            raise RuntimeError(
                f"{type(self).__name__}._execute called from within a running "
                f"event loop; await `_execute_deterministic(input, ctx)` instead."
            )

        # Save & restore the policy's current loop so we don't leave the test
        # suite without one.
        try:
            prior_loop = asyncio.get_event_loop_policy().get_event_loop()
        except RuntimeError:
            prior_loop = None

        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(
                self._execute_deterministic(input, None)  # type: ignore[arg-type]
            )
        finally:
            new_loop.close()
            if prior_loop is not None and not prior_loop.is_closed():
                asyncio.set_event_loop(prior_loop)

    # ------------------------------------------------------------------
    # The lifecycle — invoke()
    # ------------------------------------------------------------------

    async def invoke(self, input: I, *, ctx: AgentContext) -> AgentResult[O]:
        """Execute the full production lifecycle."""
        invocation_id = uuid.uuid4()
        started_at = datetime.now(UTC)
        started_ts = time.time()

        # Validate input
        if not isinstance(input, self.input_schema):
            input = self.input_schema.model_validate(  # type: ignore[assignment]
                input if isinstance(input, dict) else input.model_dump()
            )

        # Open the agent's span
        span = AgentTrace(
            parent_span_id=ctx.parent_span_id,
            case_id=ctx.case_id,
            name=self.qualified_name,
            kind=SpanKind.SUB_AGENT if self.parent else SpanKind.AGENT,
            attributes={
                "agent_class": type(self).__name__,
                "input_schema": self.input_schema.__name__,
                "output_schema": self.output_schema.__name__,
                "primary_model_size": self.primary_model.size if self.primary_model else "deterministic",
                "max_iterations": self.max_iterations,
                "quality_threshold": self.quality_threshold,
            },
        )
        if ctx.root_trace is None:
            ctx.attach_root_trace(span)
        else:
            # Attach this span under whichever span is the parent.
            # Walk the tree; in practice we just append to root since the
            # parent_span_id chain is what makes the topology explicit.
            ctx.root_trace.children.append(span)

        # Open the trace span via the pluggable sink (Postgres in prod,
        # InMemory in tests, or any custom impl).
        span_handle = await ctx.trace_sink.open_span(
            case_id=ctx.case_id,
            agent_name=self.qualified_name,
            input_payload=self._safe_dump(input),
        )

        # Per-invocation state
        cost = Cost()
        tokens = TokenUsage()
        retries = 0
        grader_score: float | None = None
        last_error: Exception | None = None
        output: O | None = None
        sub_ctx = ctx.child_for(span)
        cache_key: response_cache.CacheKey | None = None
        served_from_cache = False
        cached_model_id: str | None = None

        # Establish GenAI Gateway call context for the duration of this
        # agent invocation. Every Bedrock call inside this scope carries
        # the org_id + case_id + agent_name into llm_invocations and the
        # tenant-policy enforcement.
        gateway_token = set_call_context(GatewayCallContext(
            organization_id=ctx.organization_id,
            case_id=ctx.case_id,
            agent_name=self.qualified_name,
            request_id=getattr(ctx, "request_id", None),
        ))

        try:
            # ----- 0. Deterministic response cache (SCALE-9) -----
            # Only for LLM agents (deterministic agents already pure-Python fast).
            # On a hit, jump straight to the persistence/return block —
            # input is already validated above; the cached output passed
            # guardrails on the WRITE side, so we trust it.
            if (
                self.cache_enabled
                and self.primary_model is not None
                and ctx.organization_id  # never cache without a tenant key
            ):
                try:
                    cache_key = response_cache.CacheKey.derive(
                        agent_qualified_name=self.qualified_name,
                        organization_id=ctx.organization_id,
                        schema_version=response_cache.schema_version_for(self.output_schema),
                        input_json=input.model_dump_json(by_alias=False),
                    )
                    hit = await response_cache.lookup(cache_key)
                except Exception as cache_err:  # noqa: BLE001
                    # Never let cache infra failures block an agent run.
                    span.add_event("cache_lookup_failed", error=str(cache_err)[:200])
                    cache_key = None
                    hit = None
                if hit is not None:
                    output = self.output_schema.model_validate(hit.output_json)  # type: ignore[assignment]
                    tokens = TokenUsage(
                        input_tokens=hit.input_tokens,
                        output_tokens=hit.output_tokens,
                    )
                    cached_model_id = hit.model_id
                    span.add_event(
                        "cache_hit",
                        cache_key=cache_key.digest[:16],
                        age_seconds=round(hit.age_seconds, 2),
                        prior_hits=hit.hits_pre,
                        cached_model_id=hit.model_id,
                    )
                    served_from_cache = True

            # ----- 1. Input guardrails (skipped on cache hit) -----
            if not served_from_cache:
                for gr in self.input_guardrails:
                    gr_result = await gr.check(input, agent_name=self.qualified_name, case_id=ctx.case_id)
                    span.add_event(
                        "input_guardrail",
                        guardrail=gr.name,
                        decision=gr_result.decision.value,
                        reason=gr_result.reason,
                    )
                    if gr_result.decision == GuardrailDecision.BLOCK:
                        raise InputBlocked(gr.name, gr_result.reason)
                    if gr_result.decision == GuardrailDecision.MASK and gr_result.masked_payload is not None:
                        input = gr_result.masked_payload  # type: ignore[assignment]

            # ----- 2/3. Plan + Act (with retry-on-failure loop) -----
            # Skipped entirely on cache hit — output is already populated.
            attempt = 0
            current_model = self.primary_model
            grader_feedback: str | None = None

            while not served_from_cache and attempt < self.max_iterations:
                attempt += 1

                # ---- Reserve budget ----
                if current_model is not None:
                    estimated = estimate_cost(
                        current_model,
                        input_tokens=self.estimated_input_tokens,
                        output_tokens=self.estimated_output_tokens,
                    )
                    try:
                        reservation = ctx.budget.reserve(
                            estimated_usd=estimated,
                            estimated_input_tokens=self.estimated_input_tokens,
                            estimated_output_tokens=self.estimated_output_tokens,
                        )
                    except BudgetExceeded as be:
                        span.add_event("budget_exceeded", dimension=be.dimension)
                        raise
                else:
                    reservation = None  # deterministic — no budget needed

                # ---- Act ----
                try:
                    if current_model is None:
                        # Deterministic agent
                        output = await self._execute_deterministic(input, sub_ctx)
                        span.add_event("deterministic_execute_ok")
                    else:
                        # LLM agent — single completion call
                        user_msg = self._build_user_message(input)
                        if grader_feedback:
                            user_msg = (
                                user_msg
                                + "\n\n--- PRIOR-ATTEMPT FEEDBACK (incorporate before retrying) ---\n"
                                + grader_feedback
                            )
                        llm_response: LLMResponse = await get_llm_client().complete(
                            system=self.system_prompt,
                            user=user_msg,
                            max_tokens=current_model.max_tokens,
                            temperature=current_model.temperature,
                            model_id=resolve_model_id(current_model),
                        )

                        # Update token + cost telemetry
                        tu = TokenUsage(
                            input_tokens=llm_response.input_tokens,
                            output_tokens=llm_response.output_tokens,
                        )
                        tokens = tokens + tu
                        actual_cost = estimate_cost(
                            current_model,
                            input_tokens=llm_response.input_tokens,
                            output_tokens=llm_response.output_tokens,
                        )
                        cost = cost + Cost(
                            usd=actual_cost,
                            breakdown={current_model.size: actual_cost},
                        )
                        if reservation is not None:
                            ctx.budget.commit(
                                reservation,
                                actual_usd=actual_cost,
                                actual_input_tokens=llm_response.input_tokens,
                                actual_output_tokens=llm_response.output_tokens,
                                model_id=llm_response.model_id,
                            )

                        # Parse output
                        try:
                            output = self.output_schema.model_validate_json(  # type: ignore[assignment]
                                _strip_code_fence(llm_response.text)
                            )
                            span.add_event("llm_call_ok", model_id=llm_response.model_id)
                        except Exception as parse_err:  # noqa: BLE001
                            last_error = parse_err
                            preview = llm_response.text[:300].replace("\n", " ")
                            span.add_event(
                                "output_parse_failed",
                                error=str(parse_err)[:300],
                                response_preview=preview,
                            )
                            grader_feedback = (
                                f"Your previous output failed schema validation:\n{parse_err}\n\n"
                                f"You returned: {preview}\n\n"
                                f"Re-emit STRICT JSON conforming to the {self.output_schema.__name__} schema. "
                                f"No prose. No code fences. JSON only."
                            )
                            current_model = ModelRouter.escalate(current_model)
                            retries += 1
                            continue

                except BudgetExceeded:
                    if reservation is not None:
                        ctx.budget.cancel(reservation)
                    raise
                except Exception:
                    if reservation is not None:
                        ctx.budget.cancel(reservation)
                    raise

                # ---- Output guardrails ----
                blocked = False
                for gr in self.output_guardrails:
                    gr_result = await gr.check(
                        output, agent_name=self.qualified_name, case_id=ctx.case_id
                    )
                    span.add_event(
                        "output_guardrail",
                        guardrail=gr.name,
                        decision=gr_result.decision.value,
                        reason=gr_result.reason,
                    )
                    if gr_result.decision == GuardrailDecision.RETRY and attempt < self.max_iterations:
                        grader_feedback = f"[{gr.name}] {gr_result.reason}"
                        retries += 1
                        blocked = True
                        break
                    if gr_result.decision == GuardrailDecision.BLOCK:
                        raise OutputBlocked(gr.name, gr_result.reason)
                if blocked:
                    continue

                # ---- Reflection (if enabled) ----
                if self.quality_threshold > 0 and current_model is not None:
                    grader = self.grader or get_default_grader()
                    score, grader_usage = await grader.grade(
                        GraderInput(
                            agent_name=self.qualified_name,
                            purpose=self.description or self.role or self.name,
                            expected_schema_name=self.output_schema.__name__,
                            output_payload_json=output.model_dump_json(indent=2),
                        )
                    )
                    grader_score = score.score
                    span.add_event(
                        "grader_score",
                        score=score.score,
                        sub={
                            "schema": score.schema_correctness,
                            "clinical": score.clinical_faithfulness,
                            "citations": score.citation_completeness,
                        },
                        feedback=score.feedback[:240],
                    )
                    # Cost-account the grader's tokens too
                    g_cost = estimate_cost(
                        grader.model,
                        input_tokens=grader_usage["input_tokens"],
                        output_tokens=grader_usage["output_tokens"],
                    )
                    cost = cost + Cost(
                        usd=g_cost, breakdown={"haiku-grader": g_cost}
                    )
                    tokens = tokens + TokenUsage(
                        input_tokens=grader_usage["input_tokens"],
                        output_tokens=grader_usage["output_tokens"],
                    )

                    if score.score < self.quality_threshold and attempt < self.max_iterations:
                        grader_feedback = score.feedback
                        current_model = ModelRouter.escalate(current_model)
                        retries += 1
                        continue

                # If we got here, we're done.
                break

            # If output is still None, we exhausted iterations
            if output is None:
                raise AgentExhausted(
                    self.qualified_name, attempts=attempt, last_error=last_error
                )

            # ----- Store in deterministic response cache (SCALE-9) -----
            # Only store fresh outputs (not cache replays) and only when we
            # have a valid key. Failures here NEVER block agent success — the
            # cache is a cost lever, not a correctness primitive.
            if (
                not served_from_cache
                and cache_key is not None
                and self.cache_enabled
                and self.primary_model is not None
            ):
                try:
                    await response_cache.store(
                        cache_key,
                        agent_qualified_name=self.qualified_name,
                        organization_id=ctx.organization_id,
                        output_json=self._safe_dump(output),
                        schema_version=response_cache.schema_version_for(self.output_schema),
                        model_id=self._final_model_id_for_db(),
                        input_tokens=tokens.input_tokens,
                        output_tokens=tokens.output_tokens,
                        ttl_seconds=self.cache_ttl_seconds,
                    )
                    span.add_event("cache_store_ok", cache_key=cache_key.digest[:16])
                except Exception as cache_err:  # noqa: BLE001
                    span.add_event("cache_store_failed", error=str(cache_err)[:200])

            # ----- Emit done events + persist final agent_runs row -----
            finished_at = datetime.now(UTC)
            latency_ms = int((time.time() - started_ts) * 1000)
            span.finalize(SpanStatus.OK)
            span.attributes["retries"] = retries
            span.attributes["cost_usd"] = round(cost.usd, 6)
            span.attributes["grader_score"] = grader_score
            span.attributes["budget_remaining_usd"] = round(ctx.budget.remaining_usd, 4)
            span.attributes["served_from_cache"] = served_from_cache
            span.attributes["p95_latency_budget_ms"] = self.p95_latency_budget_ms
            if latency_ms > self.p95_latency_budget_ms:
                span.add_event(
                    "perf_budget_breach",
                    latency_ms=latency_ms,
                    budget_ms=self.p95_latency_budget_ms,
                    overage_pct=round(100 * (latency_ms - self.p95_latency_budget_ms) / self.p95_latency_budget_ms, 1),
                )

            # Audit precision: when a cache hit served the result, attribute
            # the model_id to whatever model originally produced the cached
            # output (not the *current* agent's primary model — which may have
            # changed between the original run and now). The `cache_hit` span
            # event additionally records the age and prior-hit count.
            effective_model_id = cached_model_id if served_from_cache and cached_model_id else self._final_model_id_for_db()

            await ctx.trace_sink.close_span_ok(
                span_handle,
                case_id=ctx.case_id,
                agent_name=self.qualified_name,
                output_payload=self._safe_dump(output),
                latency_ms=latency_ms,
                model_id=effective_model_id,
                input_tokens=tokens.input_tokens,
                output_tokens=tokens.output_tokens,
            )

            metadata = AgentMetadata(
                invocation_id=invocation_id,
                parent_invocation_id=None,
                agent_name=self.qualified_name,
                case_id=ctx.case_id,
                started_at=started_at,
                finished_at=finished_at,
                latency_ms=latency_ms,
                cost=cost,
                tokens=tokens,
                model_id=effective_model_id,
                model_size_used=(
                    self.primary_model.size if self.primary_model else "deterministic"
                ),
                retries=retries,
                grader_score=grader_score,
                quality_threshold=self.quality_threshold or None,
                status=SpanStatus.OK,
            )
            return AgentResult(output=output, metadata=metadata, trace=span)

        except Exception as e:
            latency_ms = int((time.time() - started_ts) * 1000)
            span.finalize(
                SpanStatus.BUDGET_EXCEEDED if isinstance(e, BudgetExceeded)
                else SpanStatus.GUARDRAIL_BLOCKED if isinstance(e, InputBlocked | OutputBlocked)
                else SpanStatus.ERROR
            )
            # The trace sink owns DB persistence + SSE publish for the
            # error event — no double-write needed here.
            await ctx.trace_sink.close_span_error(
                span_handle,
                case_id=ctx.case_id,
                agent_name=self.qualified_name,
                error=str(e),
                latency_ms=latency_ms,
            )
            raise
        finally:
            # Always reset the GenAI Gateway call context — failure mode or
            # success, the next agent's invocation must start with a clean
            # ContextVar so it can't borrow this one's tenant scope.
            reset_call_context(gateway_token)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def qualified_name(self) -> str:
        """Return `parent.name` if we have a parent; else just `name`."""
        return f"{self.parent}.{self.name}" if self.parent else self.name

    def _final_model_id_for_db(self) -> str | None:
        if self.primary_model is None:
            return None
        return resolve_model_id(self.primary_model) or f"{self.primary_model.size}-default"

    def _safe_dump(self, payload: BaseModel) -> dict[str, Any]:
        try:
            return payload.model_dump()
        except Exception:  # noqa: BLE001
            return {"_unrepresentable": True}

    def manifest_entry(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "parent": self.parent,
            "parent_agent": self.parent,  # back-compat alias for older consumers
            "qualified_name": self.qualified_name,
            "role": self.role,
            "description": self.description,
            "input_schema": self.input_schema.__name__,
            "output_schema": self.output_schema.__name__,
            "input_schema_json": self.input_schema.model_json_schema(),
            "output_schema_json": self.output_schema.model_json_schema(),
            "is_llm_backed": self.primary_model is not None,
            "primary_model": (
                {"size": self.primary_model.size, "role": self.primary_model.role}
                if self.primary_model else None
            ),
            "fallback_model": (
                {"size": self.fallback_model.size, "role": self.fallback_model.role}
                if self.fallback_model else None
            ),
            "input_guardrails": [g.manifest_entry() for g in self.input_guardrails],
            "output_guardrails": [g.manifest_entry() for g in self.output_guardrails],
            "max_iterations": self.max_iterations,
            "quality_threshold": self.quality_threshold,
            "estimated_input_tokens": self.estimated_input_tokens,
            "estimated_output_tokens": self.estimated_output_tokens,
        }


# =============================================================================
# Custom exceptions
# =============================================================================


class InputBlocked(RuntimeError):
    def __init__(self, guardrail: str, reason: str):
        self.guardrail = guardrail
        self.reason = reason
        super().__init__(f"InputBlocked[{guardrail}]: {reason}")


class OutputBlocked(RuntimeError):
    def __init__(self, guardrail: str, reason: str):
        self.guardrail = guardrail
        self.reason = reason
        super().__init__(f"OutputBlocked[{guardrail}]: {reason}")


class AgentExhausted(RuntimeError):
    def __init__(self, agent: str, *, attempts: int, last_error: Exception | None):
        self.agent = agent
        self.attempts = attempts
        self.last_error = last_error
        super().__init__(
            f"AgentExhausted[{agent}]: {attempts} attempts; "
            f"last_error={last_error!r}"
        )
