# Scientific Python Architecture

## Interface template

For each function or class document:

- purpose
- input names
- types
- shapes
- units
- coordinate system
- output
- mutation
- random behavior
- exceptions
- side effects
- performance expectations

## Suggested layers

```text
domain models
simulation adapters
estimators and controllers
learning algorithms
experiment runners
configuration
logging and schemas
analysis
reporting
```

Dependencies should normally point from orchestration toward stable domain layers, not from domain equations toward plotting or notebook state.

## Array conventions

Declare:

- time-major or feature-major
- batch dimension
- state ordering
- action ordering
- dtype
- physical or normalized values

Validate at boundaries.

## Errors

Use domain-specific exceptions for:

- invalid configuration
- infeasible optimization
- simulator unavailable
- invalid physical state
- schema mismatch
- checkpoint incompatibility
