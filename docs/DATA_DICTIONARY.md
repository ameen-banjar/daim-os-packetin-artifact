# Data Dictionary

## `interface_probe_*.csv`

- `kind`: `sizeof` or `constant`.
- `name`: C structure or constant.
- `value`: bytes for `sizeof`; integer for constants.
- Compiler and flags are recorded in the associated log and run metadata.

## `recovery_pilot.csv`

- `seed`, `repetition`: deterministic observation identity.
- `network_size`, `state_delay_ms`, `mode`: configured factors.
- `detection_ms`, `recovery_ms`, `loss_packets_modelled`, `path_stretch`,
  `control_messages_modelled`, `policy_violations_modelled`: reference-model outputs.
- Every field with `_modelled` is synthetic and must not be described as measured network performance.

## `consistency_pilot.csv`

- Factors: network size, state delay, concurrency, coordination mode.
- Outputs: residual conflicts, rollbacks, convergence, and message count from the reference model.

## `conflict_detection_pilot.csv`

- `truth`: conflict under the explicit flow/resource/policy rule.
- `prediction`: result from the selected detector.
- `tp`, `fp`, `tn`, `fn`: per-pair classification indicators.

## Summaries

Summaries contain counts, arithmetic means, population standard deviations,
medians, and p95 where meaningful. Raw rows remain the source of record.

