# Reproducing the additional service-campaign analyses

The commands below use the reproduction-package layout, where `analysis/`,
`network/`, `implementation/` and `results/` are at the package root. In the
working project those folders are under `experiments/`, except the Paper 1
documentation. This package (v1.1.1) is not the earlier v1.1.0 DOI snapshot.

## Analysis from retained records

Python 3's standard library is sufficient for the additional campaign analysis.
The raw-record audit also imports the packaged, dependency-free
`network/s56_measurement.py`. None of these commands launches a controller or
changes any raw record. Select unused output filenames; overwriting is refused.

```sh
python3 analysis/r5_service_campaign_analysis.py results/network/r5_service_campaign_20261001 --out /tmp/r5_service_reproduced.json
cmp /tmp/r5_service_reproduced.json results/network/r5_service_campaign_20261001/statistics.json
python3 analysis/r5_service_outage_interpretation.py results/network/r5_service_campaign_20261001 --out /tmp/r5_outage_reproduced.json
cmp /tmp/r5_outage_reproduced.json results/network/r5_service_campaign_20261001/outage_interpretation.json
python3 analysis/r5_service_campaign_audit.py results/network/r5_service_campaign_20261001 --out /tmp/r5_audit_reproduced.json
cmp /tmp/r5_audit_reproduced.json results/network/r5_service_campaign_20261001/raw_audit.json
python3 analysis/r5_host_resource_summary.py results/network/r5_service_campaign_20261001/host_resources.jsonl --out /tmp/r5_host_reproduced.json
cmp /tmp/r5_host_reproduced.json results/network/r5_service_campaign_20261001/host_resource_summary.json
```

The frozen descriptive analysis and supplementary outage interpretation answer
different questions. A successful post-action probe does not establish recovery
unless a preceding interruption was observed. The supplementary interpretation
was specified during collection after reviewing the first native ODL cases; it
is not a prospectively frozen analysis. The raw audit checks consistency,
including packet counts using two parsing approaches, but is not a causal proof
of the controllers' behaviour.

## Network collection is a separate reproduction task

Replaying a network campaign requires an isolated Linux lab, root access for
Mininet/OVS, compatible Python/Os-Ken, OpenFlow 1.3, the native ONOS and ODL
distributions, and both recorded Java runtimes. The original campaign used one
ARM64 VM with four virtual CPUs, about 3.81 GiB reported guest memory, and the
recorded service memory limits. Native controller binaries and a complete VM
image are not supplied by these analysis scripts.

Read `network/R5_SERVICE_CAMPAIGN_PROTOCOL.md` and the retained environment,
native-bundle, configuration and service manifests before provisioning. The
service installer has explicit paths for the author's existing lab; it is not
a portable one-command installation or permission to overwrite another lab's
services. Provision equivalent dedicated paths and verify native application
versions/configuration first. Existing controller datastores were retained in
the reported run, so a fresh installation is a new environment, not an exact
copy of the original state history.

The executed DAIM shared library links the single-Core implementation, learning
application and two OVS adapter sources. No peer protocol, distributed state
exchange or Paper 2/3 application was linked. The private original source
snapshot also captured unused distributed files through a broad file inventory;
any selective package export must list omissions explicitly rather than silently
claiming the full original source inventory is supplied.

On a provisioned lab, first run separate functional checks, including the
32-pair/66-port topology and recreated-switch socket access. Then generate a
**new** frozen plan and directory using `r5_service_campaign_supervisor.py`.
Execution verifies source hashes against that new plan. Never reuse the original
output directory or extend its sample until a desired result is obtained.
The two original amendments and failed setup record belong to the historical
run and remain retained; a new collection must document its own departures.

## What a successful package check establishes

Byte-identical statistics from this package show that the included records and
analysis reproduce the author's derived values. They do not constitute an
independent laboratory replication, demonstrate equal native applications,
resolve missing historical ping evidence, or prove hardware/distributed/failover
properties. Public release and final manuscript integration remain separate
steps.
