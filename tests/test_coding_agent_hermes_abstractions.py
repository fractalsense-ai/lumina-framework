from pathlib import Path
import importlib.util


BASE = Path(__file__).resolve().parents[1] / "model-packs" / "coding-agent"


def _load(mod_name: str, path: Path):
    spec = importlib.util.spec_from_file_location(mod_name, str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    return mod


def test_context_staging_basic():
    mod = _load("context_staging", BASE / "domain-lib" / "context_staging.py")
    assert mod.rough_tokens("hello world") == 2
    assert mod.clean_text("foo\x00  bar\n") == "foo bar"
    chunks = mod.split_words("one two three four five six", chunk_words=3, overlap_words=1)
    assert len(chunks) >= 2
    # stage selection respects max_per_path
    sample_chunks = [
        {"text": "alpha beta gamma", "path": "a"},
        {"text": "delta epsilon zeta", "path": "a"},
        {"text": "theta iota kappa", "path": "b"},
    ]
    out = mod.stage_context(sample_chunks, "alpha", budget_tokens=50, top_k=6, max_per_path=1)
    assert out["provenance"]["selected_count"] <= 2


def test_job_interpreter_and_tool_extraction():
    mod = _load("job_interpreter", BASE / "controllers" / "job_interpreter.py")
    assert mod.classify_job_mode("yes") == "execution"
    assert mod.classify_job_mode("review this") == "review"
    assert mod.classify_job_mode("what is this") == "query"
    js = '```json\n{"tool": "read_file", "args": {"path": "README.md"}}\n```'
    obj = mod.extract_tool_json_value(js)
    assert isinstance(obj, dict) and obj.get("tool") == "read_file"
    norm = mod.normalize_tool_call(obj, allowed_tools={"read_file": True})
    assert norm["tool"] == "read_file"


def test_change_request_validators():
    mod = _load("change_request", BASE / "domain-lib" / "change_request.py")
    assert mod.validate_change_branch("feat/my-topic")
    assert not mod.validate_change_branch("../bad")
    assert mod.validate_allowed_path("src/lumina/foo.py", ["src/lumina/"])
    assert not mod.validate_allowed_path("/etc/passwd", ["src/"])
