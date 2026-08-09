---
name: scientific-software-engineering
description: Design, review, and improve scientific Python and notebook-based software. Use for architecture, refactoring, interfaces, configuration, typing, units and array shapes, logging, reproducibility, error handling, path management, simulator wrappers, experiment runners, result schemas, notebooks, maintainability, and minimal safe changes. Separate plant, model, estimator, controller, agent, runner, logger, plotting, and reporting concerns while respecting the repository's active execution surface.
license: MIT
metadata:
  author: "amirhm10-research-suite"
  version: "1.0.0"
  suite: "research-engineering-suite"
  maturity: "starter"
---
# Scientific Software Engineering

## Purpose

Turn scientific methods into maintainable, traceable software without breaking the active experiment or rewriting unrelated work. Preserve scientific meaning, units, action semantics, and provenance.

## 1. Resolve the execution surface

Before editing, identify:

- actual entrypoint
- notebook-local functions
- reusable modules
- configuration
- runtime globals
- generated artifacts
- legacy or stale code
- tests
- environment
- external simulator or service

Trace the call and data path. Do not edit a helper that the active run does not use.

## 2. Define interfaces

Separate concerns where practical:

- plant or simulator
- control-oriented model
- estimator
- target selector
- optimizer
- RL agent
- safety layer
- experiment runner
- logger and result schema
- analysis and plotting
- reporting

Document inputs, outputs, units, shapes, mutation, exceptions, and side effects.

## 3. Separate configuration and state

Configuration should be explicit, serializable, and validated. Runtime state should not be hidden in module globals unless the project deliberately uses notebook state and the limitation is documented.

Use:

- dataclasses or validated structures
- clear defaults
- immutable configuration where useful
- effective-configuration saving
- one source of truth
- explicit seed objects or settings

Read [notebook-config.md](references/notebook-config.md).

## 4. Improve Python quality

For public or reused interfaces:

- type hints
- docstrings that state units and shapes
- meaningful names
- small functions
- explicit error behavior
- context managers for resources
- path objects
- structured logging
- finite-value checks
- no silent exception swallowing
- dependency injection for simulator and random state when useful

Read [python-architecture.md](references/python-architecture.md).

## 5. Preserve scientific semantics

When refactoring, verify:

- same equations
- same units
- same scaling
- same update ordering
- same random-seed behavior
- same action representation
- same solver options
- same fallback
- same logging
- same result schema

A code cleanup can invalidate scientific comparability if any of these change.

## 6. Handle notebooks carefully

- treat notebooks as structured experiment entrypoints
- inspect execution order
- avoid broad JSON-level rewrites
- extract repeated stable logic only when tests can protect it
- preserve user-owned outputs unless asked
- keep a thin orchestration narrative in notebooks
- record the kernel and environment
- avoid hidden dependence on stale cells

## 7. Design failure behavior

For solver, simulator, or plant failures:

- classify the error
- log context
- avoid silent fallback
- make fallback explicit
- preserve last valid state
- clean up owned resources
- avoid killing unrelated external processes
- allow diagnostic reproduction

## 8. Build provenance

Record:

- effective configuration
- run ID
- code version
- dirty state
- seed
- environment
- simulator case
- checkpoint
- data paths
- schema version
- analysis version

Read [provenance-logging.md](references/provenance-logging.md).

## 9. Make minimal changes

- edit authoritative files
- do not refactor unrelated code
- preserve public behavior unless change is intended
- add or update tests
- update documentation or migration notes
- list changed files
- verify with targeted tests first
- run expensive integration only when authorized

## 10. Review

Check:

- correctness
- clarity
- modularity
- scientific semantics
- tests
- performance
- resource management
- backward compatibility
- migration impact
- artifact preservation

## Gotchas

- A notebook function can be the real implementation even when a module has a similar name.
- Array broadcasting can silently change equations.
- Default mutable arguments can leak state between experiments.
- Catch-all exceptions can hide solver or simulator failure.
- Refactoring RNG use can change results despite identical seeds.
- A plot or pickle directory is not an implementation surface.
- Type correctness does not prove units or physical meaning.
