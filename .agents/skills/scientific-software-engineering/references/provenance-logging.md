# Provenance and Logging

## Run identity

Create a stable run ID and record:

- timestamp
- repository
- commit
- dirty state
- entrypoint
- configuration hash
- seed
- scenario
- environment
- simulator
- checkpoint

## Structured logs

Log machine-readable fields for:

- episode or time step
- state and action source
- proposed and executed action
- reward components
- constraints
- solver status and time
- fallback
- safety intervention
- reset and termination
- errors

## Result schema

Version the result schema. Validate required keys and coordinate systems before analysis.

## Privacy and size

Do not log secrets or sensitive raw data unnecessarily. Avoid duplicating large arrays in several formats without a provenance reason.
