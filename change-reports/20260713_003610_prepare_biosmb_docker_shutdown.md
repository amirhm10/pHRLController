# Prepare BioSMB Docker shutdown and logging behavior

## Objective

Make the existing BioSMB container forward stop signals cleanly to Python,
leave enough time for pump shutdown and the final TD3 checkpoint, and improve
build-time dependency validation without changing the proven BioSMB interface.

## Files changed

- `Biosmb-run-online/Biosmb-run-online/docker-compose.yml`
- `Biosmb-run-online/Biosmb-run-online/dockerfile`

## Implementation summary

- Explicitly selected the lowercase `dockerfile` for case-sensitive lab hosts.
- Enabled Docker's small init process for signal forwarding.
- Configured Docker to send `SIGINT`, which reaches the existing
  `KeyboardInterrupt` path in `main.py`.
- Added a 30-second stop grace period for pump shutdown and final online TD3
  checkpoint saving.
- Enabled immediate Python log output and disabled bytecode generation.
- Added `pip check` after dependency installation so inconsistent requirements
  fail during image construction.
- Kept `restart: unless-stopped`, the named model and log volumes, and the
  `main.py` development mount unchanged at the user's direction.
- Left `requirements.txt` unchanged until the new offline run completes.

## Generated artifacts

No runtime artifact or Docker image was generated.

## Verification

- `git diff --check` passed.
- The Compose indentation and Dockerfile continuation syntax were reviewed.
- Docker and a PowerShell YAML parser are unavailable on this computer, so
  `docker compose config` and a clean image build could not be run here.

## Known limitations and next steps

- Run `docker compose config` and `docker compose build` on a machine with
  Docker before sending the package to the lab.
- Revisit `requirements.txt` after the new checkpoint records its final Python,
  PyTorch, and NumPy versions.
- The existing automatic restart and volume behavior remain unchanged.
