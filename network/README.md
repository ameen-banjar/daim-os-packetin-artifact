# Stage 1 Linux/OVS Network Test

`two_switch_demo.py` creates two Open vSwitch bridges and two hosts with
Mininet. It invokes the compiled C `daim_ovs_flow` program four times to install
bidirectional forwarding rules, then verifies host connectivity and captures
the installed OpenFlow entries.

Run inside the provisioned Ubuntu VM:

```sh
./network/run_stage1.sh
```

The per-call host-clock values are smoke-test instrumentation, not a flow-setup
latency benchmark. Benchmarking begins only after clock method, warm-up,
repetitions, load, and baselines are preregistered.

