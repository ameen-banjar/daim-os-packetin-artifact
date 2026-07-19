# Stage 2 Benchmark Protocol

The first benchmark measures the cost of installing one DAIM-generated
OpenFlow 1.3 rule per switch in a real Mininet/OVS linear topology. It is an
implementation benchmark, not a superiority comparison.

- sizes: 8, 16, 32, then 64 if resources remain stable;
- repetitions: 5 per size;
- one warm topology startup per repetition;
- one rule per switch: `priority=100,ip,actions=normal`;
- per-command elapsed time: Linux monotonic host clock around the C adapter;
- connectivity check: three-packet ping from first to last host;
- recorded resources: Python harness CPU time and maximum RSS;
- all rows retained, including failed ping or failed installation.

The measured quantities are installation-command timings, not packet flow-setup
latency under offered traffic. A later benchmark must add controlled new-flow
arrival, a selected controller baseline, warm-up policy, and switch/daemon CPU
measurements before making scalability or superiority claims.

