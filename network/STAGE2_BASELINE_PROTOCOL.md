# Matched Stage 2 Baseline

The baseline repeats the stage-2 topology, rule, sizes, repetitions, ping
check, and measurement clock. The only changed factor is the invocation path:

- `daim_adapter`: compiled DAIM C adapter → `ovs-ofctl`;
- `direct_ovs`: direct `ovs-ofctl -O OpenFlow13` with the same bridge and flow.

This isolates adapter/process overhead. It is not yet a central SDN-controller
baseline and cannot establish superiority over a controller architecture.

