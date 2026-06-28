import hashlib, json, os
root = os.path.dirname(os.path.dirname(__file__))
files = [
    'model-packs/coding-agent/pack.yaml',
    'model-packs/coding-agent/cfg/runtime-config.yaml',
    'model-packs/coding-agent/cfg/ui-config.yaml',
    'model-packs/coding-agent/cfg/domain-profile-extension.yaml',
    'model-packs/coding-agent/profiles/entity.yaml',
    'model-packs/coding-agent/modules/core/module-config.yaml',
    'docs/roadmap/slices/07-coding-agent-pack-skeleton.md',
]
out = {}
for p in files:
    fp = os.path.join(root, *p.split('/'))
    try:
        with open(fp, 'rb') as f:
            h = hashlib.sha256(f.read()).hexdigest()
        out[p] = h
    except Exception as e:
        out[p] = f'ERROR: {e}'
print(json.dumps(out, indent=2))
