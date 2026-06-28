"""Deterministic Phase A pre-interpreter for coding-agent turns."""

from __future__ import annotations

from typing import Any


BOUNDARY_TERMS = (
    "bypass authority",
    "ignore system pack",
    "use credentials",
    "force push",
    "deploy without review",
)


def pre_interpret(input_text: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extract cheap authority-boundary signals before SLM interpretation."""
    text = input_text.lower()
    requested_files = [token for token in input_text.split() if "/" in token or "\\" in token]
    job_validation = None
    micro_context = None
    # Attempt to discover a job payload in the provided context or a JSON block
    job_payload = None
    if context:
        job_payload = context.get("job") or context.get("job_payload")

    # Try to extract a JSON object from fenced code or inline JSON in the input
    if job_payload is None and "{" in input_text:
        try:
            import json

            # crude extraction: take the first {...} substring
            start = input_text.index("{")
            end = input_text.rindex("}")
            candidate = input_text[start : end + 1]
            job_payload = json.loads(candidate)
        except Exception:
            job_payload = None

    # Load domain-lib helpers via file-based import to avoid package name issues
    if job_payload is not None:
        try:
            import importlib.util
            from pathlib import Path

            base = Path(__file__).resolve().parents[1] / "domain-lib"
            job_intake_path = str(base / "job_intake.py")
            micro_ctx_path = str(base / "micro_context.py")

            spec = importlib.util.spec_from_file_location("coding.job_intake", job_intake_path)
            job_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(job_mod)  # type: ignore[arg-type]

            spec2 = importlib.util.spec_from_file_location("coding.micro_context", micro_ctx_path)
            mc_mod = importlib.util.module_from_spec(spec2)
            spec2.loader.exec_module(mc_mod)  # type: ignore[arg-type]

            vres = job_mod.validate_job(job_payload)
            job_validation = {"valid": vres.valid, "errors": vres.errors, "normalized": vres.normalized}
            micro_context = mc_mod.build_micro_context(vres.normalized)
        except Exception:
            job_validation = {"valid": False, "errors": ["validation-failed"], "normalized": {}}

    return {
        "authority_boundary_hint": any(term in text for term in BOUNDARY_TERMS),
        "mentions_patch": any(term in text for term in ("patch", "diff", "edit", "modify")),
        "mentions_tests": any(term in text for term in ("test", "pytest", "validate", "ci")),
        "requested_files": requested_files,
        "job_validation": job_validation,
        "micro_context": micro_context,
    }