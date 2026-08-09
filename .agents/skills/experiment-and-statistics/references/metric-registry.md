# Metric Registry

Each project should maintain a metric registry.

| Metric | Definition | Units | Window | Aggregation | Better |
|---|---|---|---|---|---|
| IAE | \(\sum |y-r|\Delta t\) | output-unit time | stated | per output, then stated aggregate | lower |
| ISE | \(\sum (y-r)^2\Delta t\) | output-unit squared time | stated | per output | lower |
| RMSE | \(\sqrt{n^{-1}\sum(y-r)^2}\) | output unit | stated | per output | lower |
| TV input | \(\sum |u_k-u_{k-1}|\) | input unit | stated | per input | lower |
| max violation | \(\max [g(x,u)]_+\) | constraint unit | stated | per constraint | lower |
| integrated violation | \(\sum [g(x,u)]_+\Delta t\) | constraint-unit time | stated | per constraint | lower |
| evaluation return | environment-defined | reward | evaluation episodes | seed and scenario aggregate | higher |
| safety cost | cost definition | cost | evaluation episodes | seed and scenario aggregate | lower |

## Settling time

Declare:

- tolerance band
- reference value
- persistence duration
- handling of setpoint changes
- behavior when never settled

## Overshoot

Declare whether overshoot is:

- signed or absolute
- normalized by setpoint change
- computed per setpoint block
- meaningful for both directions

## Multi-output aggregation

Do not sum metrics with incompatible units unless outputs are normalized by a declared scale or weighted objective.
