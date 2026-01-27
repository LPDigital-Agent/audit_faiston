# CLAUDE.md

This file provides **GLOBAL, NON-NEGOTIABLE guidance** to Claude Code (`claude.ai/code`) for this repo.

> **CLAUDE.md MEMORY BEST PRACTICE (MANDATORY):** Root `CLAUDE.md` MUST stay **short** and universally applicable. Use **progressive disclosure**: move detailed specs to `docs/` (or module `CLAUDE.md`) and reference them here. :contentReference[oaicite:3]{index=3}

To be used on web research we are in year 2026.

---

<!-- ===================================================== -->
<!-- 🔒 IMMUTABLE BLOCK – DO NOT MODIFY OR REMOVE 🔒       -->
<!-- THIS SECTION IS PERMANENT AND NON-NEGOTIABLE          -->
<!-- ANY CHANGE, REMOVAL, OR REWRITE IS STRICTLY FORBIDDEN -->
<!-- ===================================================== -->

## 🔒 [IMMUTABLE][DO-NOT-REMOVE][AI-FIRST][AGENTIC][AWS-STRANDS][BEDROCK-AGENTCORE]

## 1) Core Architecture (NON-NEGOTIABLE)

- **AI-FIRST / AGENTIC (MANDATORY):** This system is 100% Agentic. Traditional client-server, REST-only, or “normal Lambda microservice” architecture is FORBIDDEN. Lambda is allowed ONLY as an execution substrate required by Bedrock AgentCore.

- **AGENT FRAMEWORK (MANDATORY):** ALL agents MUST use **AWS Strands Agents**.
  - Gemini provider for Strands: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/model-providers/gemini/
  - Strands official docs (source of truth):
    - https://strandsagents.com/latest/
    - https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-frameworks/strands-agents.html
    - https://github.com/strands-agents/sdk-python

- **AGENT RUNTIME (MANDATORY):** ALL agents run on **AWS Bedrock AgentCore** (Runtime + Memory + Gateway + Observability + Security).

- **A2A VIA STRANDS ONLY (IMMUTABLE & MEGA MANDATORY):** ALL Agent-to-Agent (A2A) communication MUST be done via **Strands Framework** (`A2AClientToolProvider` or `A2ACardResolver`) running on **AgentCore Runtime**. Direct HTTP calls between agents or custom A2A implementations are **STRICTLY FORBIDDEN**. This ensures protocol compliance, discovery, and observability.
  - Strands A2A Protocol: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/multi-agent/agent-to-agent/
  - Use `strands_tools.a2a_client.A2AClientToolProvider` for agent orchestration

## 2) LLM Policy (IMMUTABLE)

- **LLM POLICY (IMMUTABLE & MANDATORY):** Keep the existing rule exactly as currently defined:
  - ALL agents MUST use **GEMINI 2.5 FAMILY** (temporary change from Gemini 3).
  - CRITICAL inventory agents MUST use **GEMINI 2.5 PRO** with **THINKING ENABLED**.
  - Non-critical agents MAY use **GEMINI 2.5 FLASH**.
  - Temporary exception for Strands SDK limitations applies ONLY as currently stated.
  - Documentation:
    - https://ai.google.dev/gemini-api/docs/gemini-3
    - https://ai.google.dev/gemini-api/docs/thinking
    - https://ai.google.dev/gemini-api/docs/files

- **GEMINI VIA STRANDS ONLY (IMMUTABLE & MEGA MANDATORY):** ALL Gemini model usage MUST be done via **Strands Framework** (`strands.models.gemini.GeminiModel`). Direct Google AI API calls are **STRICTLY FORBIDDEN**. This ensures consistent agent patterns, observability, and AgentCore integration.
  - Strands Gemini Provider: https://strandsagents.com/latest/documentation/docs/user-guide/concepts/model-providers/gemini/
  - Install: `pip install 'strands-agents[gemini]'`

## 3) Source of Truth & Recency (IMMUTABLE)

- **REAL STATE OVER DOCUMENTATION (MANDATORY):** Always trust: codebase + Terraform/IaC + real AWS state. If docs disagree, reality wins.
- **RECENCY CHECK (MEGA MANDATORY):** If you are unsure or data may be outdated (we are in 2026), you MUST consult current official docs + internet before concluding.

## 4) Agent Behavior Doctrine (IMMUTABLE)

- **AGENT LOOP (IMMUTABLE & MEGA MANDATORY):** ALL agents MUST follow **OBSERVE → THINK → LEARN → ACT**, with **HUMAN-IN-THE-LOOP** always present for approvals when confidence is low or actions are high-impact.
- **NEXO AGI-LIKE BEHAVIOR (MANDATORY):** NEXO must behave AGI-like with iterative learning cycles. Before changing/documenting this behavior, explore the real codebase and validate against current best practices.

- **PROMPT LANGUAGE (IMMUTABLE):** ALL agent system prompts/tool descriptions MUST be ENGLISH. UI messages may be pt-BR.

## 5) Memory & MCP (IMMUTABLE)

- **AGENTCORE MEMORY (IMMUTABLE & MANDATORY):** Agents MUST use the Bedrock AgentCore managed memory model (STM/LTM/strategies). Do NOT implement custom memory outside AgentCore without explicit approval.
  - https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html

- **MCP ACCESS (MANDATORY):** All MCP tools/servers MUST be accessed ONLY via **AgentCore Gateway**. Never call tool endpoints directly.

- **BEDROCK AGENTCORE MCP (MANDATORY):** For communicating/testing/validating tool usage, prefer AgentCore MCP/Gateway patterns (tools/list, tools/call) and validate against current AgentCore MCP docs.

## 6) Execution Discipline (IMMUTABLE)

- **CONTEXT FIRST (MANDATORY):** Think first. Read relevant files before answering or changing anything. No speculation about code you have not opened.
- **MAJOR CHANGES REQUIRE APPROVAL (MANDATORY):** Before any major refactor/architecture change, get explicit approval.
- **SIMPLICITY FIRST (MANDATORY):** Minimal change, minimal blast radius.
- **CHANGE SUMMARY (MANDATORY):** Provide a short high-level summary of what changed and why.
- **BUGFIX DISCIPLINE (MANDATORY):** Fixes MUST be global (scan entire codebase for similar issues). Fixes MUST be executed in PLAN MODE and discussed first.

## 7) Tooling Enforcement (IMMUTABLE)

- **SUBAGENTS / SKILLS / MCP (MEGA MANDATORY):** For EVERY dev task, Claude Code MUST use SubAgents + relevant Skills + required MCP sources (Context7 + AWS docs + AgentCore docs + Terraform MCP). If not used → STOP and ask approval.

## 8) Compaction + Continuous Prime (IMMUTABLE)

- **CONTEXT WINDOW (MANDATORY):** If context > ~60% → STOP → re-read this CLAUDE.md → restate constraints + plan → use `/compact` (or `/clear` + `/prime`).
- **COMPACTION WORKFLOW (IMMUTABLE):** BEFORE `/compact`: run `/sync-project`. AFTER `/compact`: run `/prime` (or post-compact prime injection).
- **HOOKS ENFORCEMENT (MANDATORY):**
  - UserPromptSubmit MUST inject IMMUTABLE rules + `docs/CONTEXT_SNAPSHOT.md`
  - Stop MUST update `docs/CONTEXT_SNAPSHOT.md` and append `docs/WORKLOG.md`
  - If post-turn update fails → Stop hook MUST BLOCK (unless `CLAUDE_HOOKS_ALLOW_FAIL=true`)
  - Hook docs: `docs/Claude Code/HOOKS.md`  
  (Hooks events and enforcement are documented by Anthropic/Claude Docs.) :contentReference[oaicite:4]{index=4}

## 9) AWS / Infra / Security (IMMUTABLE)

- **AUTH (MANDATORY):** NO AWS Amplify. Cognito only. Direct API usage.
- **AWS CONFIG (MANDATORY):**
  - Account: `377311924364`
  - Region: `us-east-2`
  - AWS CLI profile MUST be `faiston-aio` (always pass `--profile faiston-aio`).
- **INFRA (MANDATORY):** Terraform ONLY. No CloudFormation/SAM. No local deploys. GitHub Actions only.
- **DATASTORE POLICY (CRITICAL):**
  - **Aurora PostgreSQL (RDS):** ONLY for inventory business data — inventory control, stock movements, item flows, part numbers, locations, projects, postings. This is the CORE BUSINESS datastore.
  - **DynamoDB:** EVERYTHING ELSE — audit logs, metrics, agent sessions, Agent Room events, HIL tasks, debug analytics, observability data. DynamoDB is preferred for operational/observability data.
  - **Rule:** If it's inventory business logic → Aurora. If it's system operations/observability → DynamoDB.
- **SDLC + CLEAN CODE + PYTHON (MANDATORY):** Follow SDLC, Clean Code, and Python best practices (tests, CI/CD, lint/format, types where applicable, maintainable code).
- **SECURITY (MANDATORY):** Security-first + pentest-ready (OWASP/NIST/MITRE/CIS/AWS Security/Microsoft SDL).

## 🧠 LLM = BRAIN / PYTHON = HANDS (MANDATORY)

- **LLM = "Brain"** → reasoning, planning, intent extraction
- **Python = "Hands"** → deterministic execution, parsing, validation, networking

**Key Patterns:**
- **Sandwich Pattern:** CODE → LLM → CODE (pre-process, reason, validate)
- **Tool-First:** Prefer Python functions over sub-agents when deterministic logic suffices
- **No Raw Data:** Never load full files into LLM context; use S3 references + Python processing
- **Lambda as Hands:** Deterministic operations (S3 presigned URLs, file validation, data parsing) SHOULD be extracted to Lambda microservices. Orchestrator coordinates, Lambda executes. This is NOT traditional microservices—it's "Agentic Hands" pattern.

**Full Details:** `docs/AGENTIC_ENGINEERING_PRINCIPLES.md`

9) GITHUB and DEPLOY (IMMUTABLE)

- BUG TRACKING (MANDATORY): Every bug MUST be recorded as a **GitHub Issue** (no exceptions). The issue MUST be kept updated during investigation and implementation (notes, repro steps, findings, commits/PR links). When the bug is fixed and verified, the issue MUST be **closed** with a final resolution summary.

## 10) Python Engineering (IMMUTABLE)

- **TYPE HINTS (MANDATORY):** All public functions MUST have type annotations (params + return). Use native generics (`list[str]`, not `List[str]`). Use `X | None` (not `Optional[X]`).
- **DOCSTRINGS (MANDATORY):** Google-style docstrings on all public APIs. Required sections: Args, Returns, Raises.
- **ERROR HANDLING (MANDATORY):** Specific exceptions only. NEVER use bare `except:`. Use `logging.exception()` for stack traces.
- **TESTING (MANDATORY):** pytest with 80%+ meaningful coverage. Test pyramid: 50% unit, 30% integration, 20% e2e.
- **SECURITY (MANDATORY):** OWASP 2025 patterns. No hardcoded secrets. Input validation at all entry points. Parameterized queries only.
- **TOOLING (MANDATORY):** ruff for linting/formatting, uv/poetry for dependencies. pip-audit for security scanning.
- **CLEAN CODE (MANDATORY):** SOLID principles. Functions do ONE thing. No mutable default arguments. No `print()` (use logging).

**Full Details:** `.claude/rules/infrastructure/python-best-practices.md`, `.claude/rules/infrastructure/python-security.md`

## 11) AI Agent Engineering (IMMUTABLE)

- **ARCHITECTURE (MANDATORY):** ReAct as default pattern. Multi-agent only when domain expertise separation is needed.
- **TOOL DESIGN (MANDATORY):** < 20 tools per agent (HARD LIMIT). Clear docstrings (agents decide based on these). Structured Pydantic outputs.
- **MEMORY (MANDATORY):** AgentCore memory (STM/LTM) ONLY. NO custom memory implementations without explicit approval.
- **HIL (MANDATORY):** Human-in-the-Loop for high-impact actions (DELETE, financial, bulk operations). Confidence-based escalation.
- **A2A (MANDATORY):** Strands A2A protocol ONLY (`A2AClientToolProvider`). No direct HTTP between agents.
- **OBSERVABILITY (MANDATORY):** OpenTelemetry instrumentation for all agent operations. Trace tool calls and decision steps.
- **ANTI-PATTERNS (FORBIDDEN):** God Agent (one agent does everything), Chatty Agents (text-based inter-agent comms), Cascading Failures (no circuit breakers), Stateless Assumption (no memory).

**Full Details:** `.claude/rules/agents/ai-agent-best-practices.md`

<!-- ===================================================== -->
<!-- 🔒 END OF IMMUTABLE BLOCK                             -->
<!-- ===================================================== -->

## Progressive Disclosure Index (MANDATORY)

Read these ONLY when relevant (just-in-time loading). Do NOT paste contents into root CLAUDE.md.

### Architecture (Design tasks)

| Document | When to Load |
|----------|--------------|
| `docs/AGENTIC_ENGINEERING_PRINCIPLES.md` | LLM/Python split, Sandwich Pattern |
| `docs/ORCHESTRATOR_ARCHITECTURE.md` | Agent routing, A2A protocol |
| `docs/SMART_IMPORT_ARCHITECTURE.md` | NEXO import feature |
| `docs/REQUEST_FLOW.md` | Request flow (stub → Orchestrator) |
| `docs/AUTHENTICATION_ARCHITECTURE.md` | Auth/Cognito design |

### AgentCore (Agent development)

| Document | When to Load |
|----------|--------------|
| `docs/AgentCore/IMPLEMENTATION_GUIDE.md` | AgentCore development |
| `docs/AGENTCORE_MEMORY.md` | Memory STM/LTM patterns |
| `docs/adr/ADR-005-strands-structured-output.md` | Structured output |
| `docs/TERRAFORM_AGENT_DEPLOYMENT.md` | Terraform deploy |

### Python Engineering (Code Quality)

| Document | When to Load |
|----------|--------------|
| `.claude/rules/infrastructure/python-best-practices.md` | Python development, code review, refactoring |
| `.claude/rules/infrastructure/python-security.md` | Security audit, secure development, OWASP compliance |
| `docs/AGENTIC_ENGINEERING_PRINCIPLES.md` | LLM/Python split, Sandwich Pattern |

### AI Agent Engineering (Agent Development)

| Document | When to Load |
|----------|--------------|
| `.claude/rules/agents/ai-agent-best-practices.md` | Agent development, multi-agent orchestration, tool design |
| `.claude/rules/agents/strands-framework.md` | Strands-specific patterns, Gemini integration |
| `.claude/rules/agents/cognitive-error-handler.md` | Error enrichment pattern, DebugAgent integration |

### Operations (Debug/Deploy)

| Document | When to Load |
|----------|--------------|
| `docs/TROUBLESHOOTING.md` | Error debugging |
| `docs/Claude Code/HOOKS.md` | Claude Code hooks |
| `docs/CONTEXT_SNAPSHOT.md` | Current session state |
| `docs/WORKLOG.md` | Recent activity log |

### Code Reference (Symbol lookup)

| Symbol | Purpose |
|--------|---------|
| `server/agentcore-inventory/shared/agent_schemas.py` | Response schemas |
| `server/agentcore-inventory/shared/hooks/security_audit_hook.py` | Security hook (FAIL-CLOSED) |
| `server/agentcore-inventory/agents/specialists/repair/main.py` | RepairAgent (Software Surgeon) |
