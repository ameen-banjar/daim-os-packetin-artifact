# Stage 1 Network Attempt 001 — Failed as Expected During Integration

Date: 18 July 2026

The Ubuntu environment and Linux implementation build succeeded. Mininet
created the topology, but the first flow installation failed because the OVS
bridges advertised OpenFlow 1.3 while the adapter invoked `ovs-ofctl` without an
explicit protocol, causing it to attempt OpenFlow 1.0.

Observed error:

```text
version negotiation failed (we support version 0x01, peer supports version 0x04)
ovs-ofctl: s1: failed to connect to socket (Broken pipe)
```

Corrective action: the OVS adapter was changed to pass
`-O OpenFlow13` explicitly, and its argument-vector unit test was updated.

This failed attempt is retained to preserve the integration history.

