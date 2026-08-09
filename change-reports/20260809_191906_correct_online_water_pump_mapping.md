# Correct online water pump mapping

## Objective

Correct the BioSMB online deployment configuration so the three controlled streams use pump-array indices 0, 1, and 3, with deionized water mapped to index 3.

## Files changed

- Updated `Biosmb-run-online/Biosmb-run-online/main.py`.
- Added this change report.

## Method or implementation summary

Changed `controlled_flow_indices` from `[0, 1, 2]` to `[0, 1, 3]` and changed the `controlled_stream_names` water key from `2` to `3`. The runner passes these configured indices into policy loading, online training, safety validation, logging, and pump-command handling.

## Generated artifacts

- This change report.

## Verification commands and results

- Parsed `Biosmb-run-online/Biosmb-run-online/main.py` with Python 3.14 `ast.parse`: passed.
- Inspected all `controlled_flow_indices` call sites in the online runner: the configured mapping is propagated into the deployment policy and controlled-flow checks.
- Searched the online package for dedicated tests: none were found.

## Known limitations or next steps

- No hardware-in-the-loop or pump-communication test was run.
- The online seven-pump array index is distinct from the processed lab CSV convention, where the Arium water stream remains `observation.biosmb-flows[2]`.
