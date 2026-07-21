# Stage 1 Linux/OVS Network Test

`two_switch_demo.py` creates two Open vSwitch bridges and two hosts with
Mininet. It invokes the compiled C `daim_ovs_flow` program four times to install
bidirectional forwarding rules, then verifies host connectivity and captures
the installed OpenFlow entries.

Run inside the provisioned Ubuntu VM:

```sh
./network/run_stage1.sh
```

Every script under `network/` (this one and the benchmark/comparison
scripts) needs root, for Mininet, and invokes `osken-manager` as a
subprocess. `provision_ubuntu.sh` installs that console script to
`~/.local/bin`, which is on a normal login shell's `PATH` but not on
`sudo`'s default `secure_path` -- confirmed on two independently
provisioned VMs (one ARM64, one x86-64), so budget for it rather than
treating it as a one-off. Preserve `PATH` through `sudo` explicitly:

```sh
sudo env "PATH=$PATH" python3 network/two_switch_demo.py
```

A bare `sudo python3 ...` will fail with `osken-manager: command not
found` on a fresh install.

The per-call host-clock values are smoke-test instrumentation, not a flow-setup
latency benchmark. Benchmarking begins only after clock method, warm-up,
repetitions, load, and baselines are preregistered.

