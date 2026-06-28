---
version: 0.1.0
last_updated: 2026-06-28
---

# Slice 9: Context Staging and Job Interpretation

**Version:** 0.1.0
**Status:** Planned
**Last updated:** 2026-06-28

---

## Purpose

Abstract proven patterns from the Hermes operational prototype into neutral,
authority-air-gapped coding-agent pack contracts. Three new modules provide:

1. **Context staging** — deterministic, budget-aware selection of relevant file
   chunks to include in a model prompt window without requiring embedding models.
2. **Job interpretation** — classify short affirmatives, extract and validate
   tool-call JSON, normalize tool names against an explicit allowlist.
3. **Change-request contracts** — forge-neutral validation of branch names,
   allowed paths, and change-request payloads; no GitHub-specific coupling.

The `hermesport/` directory remains an ignored, operator-local prototype.
No hermesport code is copied verbatim; only the contracts are abstracted.

---

## Scope

### A. `model-packs/coding-agent/domain-lib/context_staging.py`

| Function | Signature | Notes |
|----------|-----------|-------|
| `rough_tokens` | `(text: str) -> int` | Word-count heuristic; no external tokenizer |
| `clean_text` | `(text: str) -> str` | Strip null bytes, collapse excess whitespace |
| `split_words` | `(text, chunk_words=220, overlap_words=40) -> list[str]` | Sliding window chunker |
| `stage_context` | `(chunks, query, budget_tokens=4500, top_k=6, max_per_path=2) -> dict` | Lexical scorer; returns `{selected, summary, provenance, recall_hints}` |

**`stage_context` return shape:**
```python
{
    "selected": [{"text": str, "path": str, "score": float}, ...],
    "summary": str,            # brief human-readable provenance summary
    "provenance": {
        "budget_tokens": int,
        "selected_count": int,
        "query": str,
    },
    "recall_hints": [str, ...] # broad/low-confidence terms from query
}
```

### B. `model-packs/coding-agent/controllers/job_interpreter.py`

| Function | Signature | Notes |
|----------|-----------|-------|
| `classify_job_mode` | `(text: str) -> str` | Returns `"execution"`, `"review"`, `"query"`, or `"unknown"` |
| `extract_tool_json_value` | `(text: str) -> object \| None` | Extracts first JSON object from fenced or inline text |
| `normalize_tool_call` | `(obj: dict, allowed_tools: dict \| None) -> dict` | Validates tool name; raises `ValueError` on unknown tool if allowlist provided |
| `normalize_tool_calls` | `(text: str, allowed_tools: dict \| None) -> list[dict]` | Combines extraction + normalization; returns `[]` on parse failure |

**`classify_job_mode` rules:**
- Short affirmatives (`"yes"`, `"ok"`, `"go"`, `"sure"`, `"proceed"`, `"do it"`) → `"execution"`
- Contains `"review"`, `"check"`, `"inspect"`, `"read"` → `"review"`
- Contains `"what"`, `"how"`, `"why"`, `"explain"`, `"list"` → `"query"`
- Otherwise → `"unknown"`

### C. `model-packs/coding-agent/domain-lib/change_request.py`

| Function | Signature | Notes |
|----------|-----------|-------|
| `validate_allowed_path` | `(path: str, allowed_prefixes: list[str]) -> bool` | Rejects absolute paths and paths outside allowed prefixes |
| `validate_change_branch` | `(branch: str) -> bool` | Rejects `..`, `@{`, leading/trailing `/`, whitespace, empty strings |
| `normalize_change_request_request` | `(payload: dict) -> dict` | Returns canonical shape; raises `ValueError` on missing required fields |

**`normalize_change_request_request` output shape:**
```python
{
    "title": str,
    "description": str,
    "branch": str,
    "files_changed": list[str],
    "author": str | None,
    "metadata": dict,
}
```

---

## Out of Scope

- FastAPI, SentenceTransformer, numpy, SQLite, Docker, vLLM
- GitHub CLI (`gh pr create`), subprocess git automation
- Live model calls, network calls, credential handling
- Copying hermesport/ code verbatim into the pack
- Changing `src/lumina/` core code
- Modifying existing domain-physics invariants

---

## Required Changes

| Action | Path |
|--------|------|
| CREATE | `model-packs/coding-agent/domain-lib/context_staging.py` |
| CREATE | `model-packs/coding-agent/controllers/job_interpreter.py` |
| CREATE | `model-packs/coding-agent/domain-lib/change_request.py` |
| CREATE | `tests/test_coding_agent_hermes_abstractions.py` |
| UPDATE | `model-packs/coding-agent/CHANGELOG.md` (add 0.3.0) |
| UPDATE | `docs/roadmap/README.md` (Slice 9 status → Delivered) |
| UPDATE | `docs/MANIFEST.yaml` + regen |

---

## Files Likely Touched

```
model-packs/coding-agent/
  domain-lib/
    context_staging.py     ← new
    change_request.py      ← new
  controllers/
    job_interpreter.py     ← new
tests/
  test_coding_agent_hermes_abstractions.py ← new
docs/
  MANIFEST.yaml            ← updated (regen)
  roadmap/README.md        ← status update
  roadmap/slices/09-...md  ← this file, status → Delivered
model-packs/coding-agent/
  CHANGELOG.md             ← 0.3.0 entry
```

---

## Acceptance Criteria

**Context staging:**
- `rough_tokens("hello world")` returns `2`
- `clean_text("foo\x00bar")` returns `"foobar"` (null stripped)
- `split_words(long_text, chunk_words=5, overlap_words=1)` produces overlapping chunks where consecutive chunks share the last word of the previous chunk
- `stage_context(chunks, query, budget_tokens=50, top_k=6, max_per_path=1)` returns no more than one chunk per unique path
- `stage_context` does not exceed `budget_tokens` in total selected token count

**Job interpretation:**
- `classify_job_mode("yes")` → `"execution"`
- `classify_job_mode("ok go")` → `"execution"`
- `classify_job_mode("review this carefully")` → `"review"`
- `classify_job_mode("what does this do?")` → `"query"`
- Fenced JSON ` ```json\n{"tool": "read_file"}\n``` ` extracted correctly by `extract_tool_json_value`
- Unknown tool name in `normalize_tool_call` with a non-`None` allowlist raises `ValueError`

**Change-request:**
- `validate_change_branch("feat/my-topic")` → `True`
- `validate_change_branch("../bad")` → `False`
- `validate_change_branch("bad@{upstream}")` → `False`
- `validate_allowed_path("src/lumina/foo.py", ["src/lumina/"])` → `True`
- `validate_allowed_path("/etc/passwd", ["src/"])` → `False`
- `validate_allowed_path("../../escape.py", ["src/"])` → `False`

---

## Tests

**File:** `tests/test_coding_agent_hermes_abstractions.py`

Grouped into three classes or sections:
1. `TestContextStaging` — covers `rough_tokens`, `clean_text`, `split_words`, `stage_context` budget and max_per_path constraints
2. `TestJobInterpreter` — covers all four `classify_job_mode` branches, JSON extraction from fenced and inline text, unknown-tool rejection
3. `TestChangeRequest` — covers branch validation (valid and invalid patterns), path validation, `normalize_change_request_request` happy path and missing-field error

All tests: no network, no live model, no subprocess calls, no credentials.

---

## Ledger / Governance Impact

None. New domain-lib helpers operate inside the coding-agent pack boundary.
No authority gate logic, domain registry, or core engine invariants are changed.

---

## Follow-Up Slices

**Slice 10:** Tool-Adapter Policy Enforcement — introduce deny-by-default
`tool_call_policies` blocks in `domain-physics.json` and validate that
`normalize_tool_call` respects the policy before routing any tool request.
