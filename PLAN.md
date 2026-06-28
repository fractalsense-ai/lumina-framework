# PLAN.md — Lumina Framework Execution Plan
# Slice 8: Abstract Hermes Prototype into Coding Agent Pack

> Target Agent: qwen2.5-coder-14b-instruct-awq
> Context Window: 32k
> Tools: context7, sequential_thinking, local file read/write, terminal
> Date: 2026-06-28

## Objective

Abstract the reusable architecture proven in the ignored `hermesport/` prototype into the Lumina `model-packs/coding-agent/` model pack.

This PR must turn Hermes-specific middleware behavior into Lumina-native Coding Agent pack contracts and deterministic helpers. The Coding Agent remains an authority-air-gapped artifact factory. It must not become a Hermes proxy, vLLM proxy, credential holder, deployment system, or GitHub-only workflow.

Important prerequisite: verify that `model-packs/coding-agent/` exists before implementing Slice 8. If it does not exist in the current branch, stop and restore or complete the Slice 7 coding-agent skeleton first. Do not combine Slice 7 skeleton creation and Slice 8 Hermes abstraction in one PR unless explicitly instructed.

## Context Needed

Use `context7` only for live API details if implementation requires them:

- `pydantic` only if creating typed request/result models
- `pytest` only if test patterns or fixtures are unclear
- `pyyaml` only if reading/writing runtime YAML safely
- `jsonschema` only if validating new JSON contracts
- MCP protocol docs only if preserving the PR workflow as a future adapter contract

Do not query vLLM, FastAPI, Docker, GitHub Actions, or sentence-transformers docs unless the PR explicitly keeps those dependencies. The goal is abstraction, not copying the Hermes services.

Read these local files first:

- `PLAN.md`
- `docs/roadmap/slices/06-coding-agent-model-pack-architecture-v2.md`
- `model-packs/coding-agent/pack.yaml`
- `model-packs/coding-agent/cfg/runtime-config.yaml`
- `model-packs/coding-agent/controllers/runtime_adapters.py`
- `model-packs/coding-agent/modules/coding-agent-core/domain-physics.json`
- `model-packs/system/cfg/domain-registry.yaml`
- `tests/test_schema_versioning.py`
- `hermesport/context_stager.py`
- `hermesport/vllm_guard_proxy.py`
- `hermesport/mcp_pr_workflow_server.py`
- `hermesport/system_execution.md`
- `hermesport/PR_WORKFLOW.md`

Use `sequential_thinking` after reading the Hermes files to verify which pieces are reusable pack logic and which pieces are operational glue.

## Execution Steps

1. Verify that `model-packs/coding-agent/` exists.

2. If `model-packs/coding-agent/` is missing, stop and report:
   `Slice 7 coding-agent skeleton is missing in this checkout. Restore that branch or run the Slice 7 skeleton PR first.`

3. Verify that `model-packs/coding-agent/pack.yaml` contains version and last_updated header comments required by `tests/test_schema_versioning.py`.

4. Read `hermesport/context_stager.py` and identify only the reusable concepts:
   - chunking
   - rough token estimation
   - path-aware context selection
   - budget-aware selection
   - provenance metadata
   - recall hints

5. Do not copy FastAPI endpoints, global `SentenceTransformer` startup, SQLite service lifecycle, or runtime DB paths into the model pack in this PR.

6. Create a Coding Agent domain-lib module for context staging, for example:
   `model-packs/coding-agent/domain-lib/context_staging.py`

7. Implement deterministic, dependency-light helpers in that module:
   - `rough_tokens(text: str) -> int`
   - `clean_text(text: str) -> str`
   - `split_words(text: str, chunk_words: int = 220, overlap_words: int = 40) -> list[str]`
   - `stage_context(chunks, query, budget_tokens=4500, top_k=6, max_per_path=2) -> dict`

8. Keep `stage_context` lexical or score-injected for now. Do not require MiniLM, sentence-transformers, numpy, FastAPI, or SQLite in this PR.

9. Ensure `stage_context` returns a Lumina-shaped packet:
   - `selected`
   - `summary`
   - `provenance`
   - `recall_hints`

10. Read `hermesport/vllm_guard_proxy.py` and identify reusable concepts only:
    - mode classification
    - short affirmative routing to execution
    - tool-name normalization
    - safe filesystem path normalization
    - parent directory preflight intent
    - plain-text JSON tool-call extraction
    - max-token safety policy

11. Do not copy the HTTP proxy, vLLM upstream calls, stream/SSE handling, Hermes-specific prompt injection, or environment-variable driven service behavior.

12. Create a Coding Agent controller/helper module, for example:
    `model-packs/coding-agent/controllers/job_interpreter.py`

13. Implement deterministic helpers:
    - `classify_job_mode(text: str) -> str`
    - `extract_tool_json_value(text: str) -> object | None`
    - `normalize_tool_call(obj: dict, allowed_tools: dict | None = None) -> dict`
    - `normalize_tool_calls(text: str, allowed_tools: dict | None = None) -> list[dict]`

14. Use Lumina-neutral names. Do not use `Hermes`, `vLLM`, `Desktop`, or provider-specific names in new pack APIs unless documenting prototype provenance.

15. Read `hermesport/mcp_pr_workflow_server.py` and identify reusable concepts only:
    - allowed path validation
    - safe branch validation
    - PR metadata normalization
    - pack.yaml header hygiene
    - manifest tracking requirement
    - schema preflight before PR creation

16. Do not copy `gh pr create`, subprocess git automation, stdio MCP server loop, or GitHub-only behavior into the pack core.

17. Create a forge-neutral PR/change-request contract module, for example:
    `model-packs/coding-agent/domain-lib/change_request.py`

18. Implement data structures or pure helpers for:
    - `validate_allowed_path(path: str, allowed_prefixes: list[str]) -> bool`
    - `validate_change_branch(branch: str) -> bool`
    - `normalize_change_request_request(payload: dict) -> dict`

19. Name the abstraction `change_request`, not `pull_request`, where possible. GitHub PRs are one adapter posture, not the architecture.

20. Update `model-packs/coding-agent/cfg/runtime-config.yaml` to expose new conceptual adapter/tool policy stubs only if the existing config pattern supports it.

21. Add or update `tool_call_policies` in the coding-agent domain physics/config so tool access is explicit and deny-by-default.

22. Add tests in a focused file such as:
    `tests/test_coding_agent_hermes_abstractions.py`

23. Test context staging:
    - chunks are cleaned
    - overlap works
    - budget limits selected chunks
    - `max_per_path` is respected
    - provenance contains budget and selected count
    - broad/low-confidence recall hints are deterministic

24. Test job/mode interpretation:
    - `"yes"`, `"ok"`, `"go"`, `"sure"` classify as execution
    - `"review this"` classifies as review
    - JSON/fenced JSON tool calls are extracted
    - unknown tool names are not silently granted authority

25. Test change-request helpers:
    - safe `hermes/topic` or `agent/topic` style branch passes if allowed by the helper
    - branch names with `..`, `@{`, leading slash, or trailing slash fail
    - paths outside allowed prefixes fail
    - relative allowed paths pass

26. Update `model-packs/coding-agent/README.md` with a short section:
    `Hermes Prototype Abstraction`
    Explain that `hermesport/` remains an ignored operational prototype, while the coding-agent pack now owns the neutral contracts.

27. Add a Slice 8 roadmap doc only if this PR is intended to be the formal Slice 8 deliverable:
    `docs/roadmap/slices/08-hermes-prototype-abstraction.md`

28. If a Slice 8 doc is added, update `docs/roadmap/README.md`.

29. Update `docs/MANIFEST.yaml` for any new docs or model-pack YAML files required by existing manifest/versioning tests.

30. Do not add `hermesport/` to git. It is ignored and should remain prototype/operator-local material.

31. Do not modify `.gitignore` unless explicitly asked.

32. Do not modify `src/lumina/` core code in this PR.

33. Do not add live model calls, network calls, Docker dependencies, vLLM dependencies, GitHub CLI dependencies, or local service startup requirements.

34. Run focused tests first.

35. Fix only failures in the touched Coding Agent pack surface.

36. Run schema/versioning tests.

37. Run the full relevant backend suite or the repository’s current CI command.

## CI/CD Requirements

Run from repository root:

```bash
python -m pytest tests/test_coding_agent_hermes_abstractions.py -q
```