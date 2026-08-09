# Notebooks and Configuration

## Notebook role

A notebook may be:

- exploratory analysis
- authoritative experiment entrypoint
- report
- visualization
- migration wrapper

Identify the role before editing.

## Safe notebook practices

- inspect cell order
- identify definitions and globals
- preserve markdown context
- avoid stale output assumptions
- use named configuration cells or imported config
- save effective config
- keep expensive execution optional
- provide smoke mode
- restart-and-run validation when practical

## Configuration

Prefer:

- validated dataclasses
- YAML or TOML where appropriate
- explicit algorithm and plant sections
- units
- defaults
- schema version
- serialization

Avoid configuration spread across notebook cells, globals, filenames, and hidden defaults.
