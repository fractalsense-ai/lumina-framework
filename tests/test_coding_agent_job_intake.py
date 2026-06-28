import json
from pathlib import Path
import importlib.util


BASE = Path(__file__).resolve().parents[1] / "model-packs" / "coding-agent" / "domain-lib"


def _load(mod_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def test_validate_job_ok():
    job_mod = _load("job_intake", BASE / "job_intake.py")
    payload = {"title": "Add README", "description": "Add a README explaining usage.", "priority": "normal"}
    res = job_mod.validate_job(payload)
    assert res.valid
    assert res.normalized["priority"] == "normal"


def test_validate_job_missing_fields():
    job_mod = _load("job_intake", BASE / "job_intake.py")
    payload = {"title": "", "description": "short"}
    res = job_mod.validate_job(payload)
    assert not res.valid
    assert "missing-or-invalid-title" in res.errors


def test_pre_interpret_extracts_micro_context():
    pre_mod_path = Path(__file__).resolve().parents[1] / "model-packs" / "coding-agent" / "controllers" / "nlp_pre_interpreter.py"
    pre_mod = _load("nlp_pre", pre_mod_path)

    job_payload = {"title": "Refactor", "description": "Refactor module for clarity", "priority": "high"}
    input_text = "Please do this job: " + json.dumps(job_payload)
    result = pre_mod.pre_interpret(input_text, context=None)

    assert result.get("job_validation") is not None
    assert result.get("micro_context") is not None
    assert result["job_validation"]["valid"]
    assert result["micro_context"]["tier"] == "critical"
