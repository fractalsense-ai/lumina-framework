import importlib.util
import sys
import pathlib
import subprocess
from unittest.mock import patch, MagicMock


ROOT = pathlib.Path(__file__).parent.parent


def load_module(path: str, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    # Ensure module is visible to dataclasses and other introspection
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_build_and_check_policy_allow():
    tp = load_module(str(ROOT / "model-packs" / "coding-agent" / "domain-lib" / "tool_policies.py"), "tp")
    policy = tp.build_default_policy(["a", "b"])
    req = tp.ToolCallRequest(tool_id="a", payload={"k": 1}, caller_context={})
    allowed, reason = tp.check_tool_call(req, policy)
    assert allowed and reason == ""


def test_build_and_check_policy_deny_unknown():
    tp = load_module(str(ROOT / "model-packs" / "coding-agent" / "domain-lib" / "tool_policies.py"), "tp")
    policy = tp.build_default_policy(["a"])
    req = tp.ToolCallRequest(tool_id="z", payload={"k": 1}, caller_context={})
    allowed, reason = tp.check_tool_call(req, policy)
    assert not allowed and reason.startswith("tool_not_allowed")


def test_run_tests_tool_success_and_unauthorized(tmp_path):
    ta = load_module(str(ROOT / "model-packs" / "coding-agent" / "controllers" / "tool_adapters.py"), "ta")

    # Successful run: mock subprocess.run
    mock_cp = subprocess.CompletedProcess(args=["pytest"], returncode=0, stdout="1 passed", stderr="")
    with patch("subprocess.run", return_value=mock_cp):
        res = ta.run_tests_tool({"commands": ["pytest -q"], "working_dir": str(ROOT)})
        assert res.get("tests_passed") is True

    # Unauthorized command
    res2 = ta.run_tests_tool({"commands": ["rm -rf /"]})
    assert res2.get("tests_passed") is False and res2.get("output") == "unauthorized_command"


def test_run_tests_tool_timeout(tmp_path):
    ta = load_module(str(ROOT / "model-packs" / "coding-agent" / "controllers" / "tool_adapters.py"), "ta")

    def raise_timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=args[0], timeout=1)

    with patch("subprocess.run", side_effect=raise_timeout):
        res = ta.run_tests_tool({"commands": ["pytest -q"], "working_dir": str(ROOT)})
        assert res.get("tests_passed") is False and res.get("output") == "timeout"
