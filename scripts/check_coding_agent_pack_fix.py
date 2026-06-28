import json, yaml, sys
from pathlib import Path
from jsonschema import validate

root=Path(__file__).resolve().parents[1]
rc = yaml.safe_load((root/"model-packs/coding-agent/cfg/runtime-config.yaml").read_text())
tools = rc.get("tools", {})
expected = [
    "adapter/ca/read-file/v1",
    "adapter/ca/write-file/v1",
    "adapter/ca/run-tests/v1",
    "adapter/ca/stage-patch/v1",
]
missing=[t for t in expected if t not in tools]
if missing:
    print("MISSING", missing)
    sys.exit(2)
physics = json.loads((root/"model-packs/coding-agent/modules/core/domain-physics.json").read_text())
schema = json.loads((root/"standards/domain-physics-schema-v1.json").read_text())
validate(instance=physics, schema=schema)
print("VALIDATION OK")
