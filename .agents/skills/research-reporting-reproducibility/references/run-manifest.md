# Run Manifest Template

```yaml
run_id: ""
created_at: ""
repository: ""
git_sha: ""
git_dirty: null
entrypoint: ""
configuration_file: ""
configuration_hash: ""
environment:
  name: ""
  python: ""
  packages_lock: ""
simulator:
  product: ""
  version: ""
  case_file: ""
  scenario: ""
model_or_checkpoint: ""
seed: null
sample_time: null
horizon_or_duration: null
data_paths: []
analysis_scripts: []
figure_paths: []
metric_registry: ""
notes: []
missing_provenance: []
```

## Rules

- Use `null` or `missing_provenance` rather than guessing.
- Record physical units and scaling artifact versions elsewhere in the project profile or manifest.
- If a notebook contains the active implementation, record the notebook and relevant cell or function.
- Hash configuration files or serialize the effective configuration when possible.
