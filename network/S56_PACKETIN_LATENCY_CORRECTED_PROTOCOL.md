# Corrected protocol for the reactive Packet-In stage-latency experiment (§5.6/§6.2.1)

**Status: implementation verified; official collection not yet started at this checkpoint.
Historical data and `packetin_latency_breakdown_raw.csv` (90 rows, the current
published sample) has not been touched.** This document exists to be
approved or amended before any implementation work starts, per the
decision that I1 requires a corrected re-run, not a reinterpretation of
the old data.

## 1. Why the old data cannot be kept for this specific claim

`packetin_latency_breakdown.py`'s capture condition (`daim_bridge_controller.py`)
is `not self._captured and ip_pkt.dst == TARGET_IP` — destination only,
no source or in-port check. The trial sequence sends an untimed h3->h2
warm-up ping before the timed h1->h2 ping, and `TARGET_IP` is armed from
controller start-up, before either ping is sent. Tracing where `installed`
is set (`daim_learning_app.c:135-140`) shows it is written unconditionally
once the destination is known, not gated on `install_flow()`'s result; and
`confirmed` (`dl_dst=<mac>` substring in `dump-flows`) proves a matching
flow exists, not that this specific capture created it, since no
pre-flight snapshot is taken to establish its prior absence. Neither field
compensates for the missing source check. No stored field in the raw CSV
identifies which host's packet was captured, so the question is not
resolvable from the existing 90 trials.

## 2. Decision

- **Old data (`packetin_latency_breakdown_raw.csv`, 90 rows) is kept
  unmodified**, reclassified as insufficient to support the specific
  claim "this measures h1's packet after an unmeasured warm-up." Not
  deleted, not silently reinterpreted.
- **A corrected experiment is prepared** for the same three modes as the
  original: DAIM process-per-rule, DAIM persistent, reactive Os-Ken
  (DAIM-free baseline).

## 3. Corrected protocol requirements

Identity and sequencing are both **mandatory and simultaneous**, not one
a fallback for the other: capture must not start before warm-up's end
is independently confirmed, and once started it must accept nothing but
the specific target packet.

### A. Identity condition

The original proposal (source IP + destination IP only) is too narrow.
The capture/acceptance condition for the timed record now requires, all
together: trial ID, bridge/switch name, ingress port, source MAC,
destination MAC, source IP, destination IP, and ethernet/IP protocol
type. Since the timed packet is ICMP, it additionally requires ICMP
type (echo request, `type=8`), ICMP identifier, and ICMP sequence
number, extracted from the packet -- this is what distinguishes the one
specific request from a retransmission or from the echo reply travelling
the other direction (which has the same source/destination pair
reversed and would otherwise be a near-miss).

Two distinct moments are kept separate, not conflated:
- **Entry timestamp**: captured at the first processor touch for *every*
  packet reaching the handler (as the implementation already does
  unconditionally today) -- this is bookkeeping, not an acceptance
  decision.
- **Record acceptance**: the emitted timing record is only produced for
  a packet that (a) matches the full identity above *and* (b) arrives
  after capture has been explicitly activated (see B below). A packet
  that only partially matches, or arrives before activation, produces no
  record at all -- not a discarded one, an absent one, so it cannot be
  mistaken later for a completed trial.

**ARP is resolved at the host level, with no wire traffic, so it cannot
itself install the rule under measurement.** The earlier plan (h1 and h2
exchange real ARP requests/replies before the measured window) was
self-defeating: h2's ARP request would draw a unicast reply from h1
that travels through `packet_in -> learn -> lookup -> possibly install`
exactly like IP traffic does, and could install `in_port=h1,
dl_dst=h2` -- the very rule the experiment exists to measure the
creation of -- before the timed packet is ever sent. The pre-flight
check would catch this, but only by invalidating the trial because of
the protocol's own setup step, not because of anything the system under
test did.

Instead: h1's and h2's neighbour tables are populated directly on each
host (e.g. `ip neigh replace <peer-ip> lladdr <peer-mac> dev <iface> nud
permanent`), so each host already knows the other's MAC address without
a single ARP frame crossing the switch. Controller-side warm-up remains
h3<->h2 only, as before. The sequence is: install neighbour entries on
h1 and h2 -> verify the entries are present -> verify the target rule
is still absent (C) -> only then activate capture and send. A host
knowing a peer's MAC address is not the same fact as the controller
having learned that peer's location; only an actual packet-in through
the controller does that, and this setup produces none for the h1/h2
pair before the timed packet.

### B. Warm-up completion is verified functionally -- not read from the internal learning table, and not claimed to pinpoint the moment of learning

Seeing *a* rule mentioning h3 does not prove what matters, and neither
does seeing the reply-direction rule alone: a rule can in principle
predate the exchange it's being used as evidence for, and matching one
rule does not expose the Core's internal source table directly. No
function in the current public API (`daim_learning_app_stats`,
`daim_learning_app_last_timing`) exposes a direct "is MAC X known, at
which port" query without adding new internal plumbing, so this is
resolved functionally rather than by instrumenting the Core further
just to justify the word "just":

The two-ping warm-up (unchanged from the original design) is expected,
by the controller's own learn/lookup logic, to produce rules in *both*
directions by the time it finishes: the first reply (h2->h3) teaches h2
and installs `in_port=<h2's port>, dl_dst=<h3's mac>,
actions=output:<h3's port>`; the second request (h3->h2), now that h2 is
known, installs `in_port=<h3's port>, dl_dst=<h2's mac>,
actions=output:<h2's port>`. The harness confirms **both** rules are
present (per-field, per C) before proceeding. This is reported and
documented as **functional verification that the warm-up exchange
completed and that routing in both directions is ready** -- not as a
claim to know the exact instant either host was learned, and not as a
read of internal state. If either expected rule is not observed within
a bounded timeout, the trial does not proceed silently; see E.

### C. Rules are parsed into fields, never matched as one literal string

`dump-flows`'s field order is not guaranteed to match the exact sequence
written in code. Each rule line is parsed into its constituent fields
(`in_port`, `dl_dst`, `priority`, `actions`) independently, and each
field's *value* is checked against the expected value -- not a single
concatenated string compared against the raw line. This applies equally
to the pre-flight check (D in the original draft's numbering, folded in
here) and the post-send confirmation.

The pre-flight check does not assume that *any* broader or lower-priority
rule necessarily blocks the target packet from reaching the controller --
that is not always true (a higher-priority rule can still forward it to
the controller over a broader, lower-priority one), and asserting it
would overstate what the check actually establishes. For this
experiment's known, fixed topology the check is instead bounded and
concrete: the warm-up phase installs exactly two expected exact-match
rules (B), both priority 100, and the switch's only other rule is the
default priority-0 send-to-controller miss rule. The pre-flight check
(i) enumerates the warm-up-expected rules and confirms there are no
others, and (ii) confirms neither expected rule's match fields
(`in_port` + `dl_dst` together) equal the target packet's own
`(in_port=h1's port, dl_dst=h2's mac)` -- which is sufficient here
because these are exact-match rules with identical field semantics, not
a general claim about priority ordering under wildcards. Any rule the
parser does not recognise (an unexpected match pattern or an action it
cannot classify) is treated explicitly as **a deviation from the
expected experimental setup** and the trial is rejected on that basis --
not silently ignored, and not asserted to have definitely blocked
arrival either.

### D. Explicit time boundary, not a promise to unify it later

- **Start**: the target packet (matching A's full identity) entering the
  application handler -- the existing `t_dispatch_enter` timestamp, now
  tied to an accepted record rather than every packet.
- **End**: completion of the *first successful read* that confirms the
  target rule via the per-field check in C.
- **Name**: handler-entry-to-rule-observed time. Explicitly not a
  measurement of OVS's internal rule-application time alone -- it also
  includes whatever the confirmation polling itself costs, the same
  caveat already stated elsewhere in this artifact for the equivalent
  stage.
- **Polling start, fixed and stated**: confirmation polling begins
  immediately after `PacketOut` is sent (matching the existing
  implementation's order: install call, then `PacketOut`, then the first
  poll) -- stated explicitly here rather than left as an implicit
  consequence of code order.
- **Every poll attempt is logged**, not only the final successful one:
  each attempt's own start time, end time, exit code, and whether the
  target rule's fields matched, recorded as a list per trial (the same
  pattern already used for the restart-recovery experiment's Q3
  monitor), so a slow or erroring poll is visible in the data, not only
  in the final pass/fail outcome.

### E. Outcome recorded as independent fields, not one exclusive category

A single three-way category cannot represent this experiment honestly:
success was missing from it; a `ping` failure and a rule-confirmation
timeout can happen in the same trial without one implying the other; and
the rule can be confirmed while the reply never arrives (or the reverse).
Each trial instead records four independent fields:

| Axis | Possible values |
|---|---|
| Protocol compliance | Met / setup deviation (with a stated reason -- e.g. the C check above) |
| Target event | Observed / not observed / wrong identity observed instead |
| Connectivity (ping) | Succeeded / failed / could not be assessed |
| Rule observation | Confirmed (full per-field match) / timed out / tool error |

A legitimate warm-up-confirmation failure (B's expected rules not
observed in time, with the monitor itself healthy) is **not**
auto-classified as a tool malfunction -- it is recorded as a genuine
readiness-failure result on the "target event" / "rule observation"
axes. Likewise, the target event simply not being observed does not, on
its own, mean the measurement tool broke; "tool error" is reserved for
cases where the monitoring mechanism itself demonstrably failed
(non-zero `dump-flows` exit, a ping-parser disagreement against its own
exit code, an unparseable rule per C). What counts as in-scope for the
timing analysis versus reported separately is fixed from these four
fields before collection, not decided per trial while looking at
results.

### F. Every attempt is saved

Every trial is written to the raw output with its full set of four
fields from E, regardless of outcome. Which field-value combinations are
in scope for the timing analysis, versus reported separately, is fixed
before collection -- no post-hoc selective replacement of trials.

## 4. Sample and schedule

**30 blocks**, each block containing a trial of **all three modes** in a
randomised order fixed per block and saved before collection (the same
block/schedule discipline as the restart-recovery experiment, extended
from two arms to three). This is 90 scheduled attempts total -- the
schedule is run to completion once, it is not "collect until 90
successes"; whatever each attempt's four-field outcome (E) turns out to
be is what gets recorded.

Before collection, fixed in the protocol: the primary pairwise
comparisons (persistent vs. process-per-rule, persistent vs. reactive
Os-Ken, process-per-rule vs. reactive Os-Ken), and the resampling unit
for any bootstrap analysis -- resampling is done **by block**, preserving
the three-mode pairing within each block, the same reasoning the
restart-recovery experiment already applies to its own block-bootstrap.

30 is not justified as sufficient for tail-percentile (p95/p99)
precision, and no power calculation is derived from the old,
identity-unverified data's observed differences -- this is a bounded
estimation design, not a guarantee of detecting a difference or
resolving the tail.

### Timeout and interval parameters (filled in before the schedule is frozen)

| Parameter | Value | Where it applies |
|---|---|---|
| Controller readiness timeout | 20 s | Waiting for the controller's own ready signal at trial start |
| Warm-up confirmation timeout | 5 s | Polling for both B-expected rules after the warm-up exchange |
| Warm-up confirmation poll interval | 50 ms requested sleep after each poll | Spacing between `dump-flows` polls during B |
| Target-rule confirmation timeout | 3 s | Polling for the timed packet's own rule (D) |
| Target-rule confirmation poll interval | 0.5 ms requested sleep after each poll | Spacing between `dump-flows` polls during D |
| `ping` per-attempt timeout (`-W`) | 1 s | The timed connectivity check |
| Each external call's own subprocess timeout (`ovs-vsctl`, `dump-flows`, `ping`) | ovs-vsctl: 5 s; dump-flows: min(1 s, remaining observation budget); ping process: count*(1+1)+2 s | Distinct from the polling timeouts above -- how long a single invocation of the tool itself is allowed to hang before being treated as a tool error |

This table is populated with concrete numbers as part of finalising this
protocol, before the pre-collection verification in Section 5 is run
against them -- not left as placeholders once collection starts.

### Policy for an incomplete block (one mode fails, the others in the same block succeed)

- **No substitution.** A missing or non-confirmed time is never replaced
  with zero or with the timeout bound in any computation.
- **No deletion.** The block is not dropped from the overall results
  report because one of its three trials did not produce a confirmed
  time -- the other two modes' results from that block remain in the
  overall (non-paired) per-mode analysis.
- **Paired/block-resampling analyses** (the by-block bootstrap in this
  section) use only blocks where the specific pair being compared both
  have a confirmed time; this is a narrower, explicitly-labelled subset
  of blocks, not silently assumed to be all 30.
- **Any statistic computed only over confirmed times** -- whether it is
  the overall per-mode median or a paired comparison -- is labelled
  explicitly as conditional on success (matching the restart-recovery
  experiment's own convention for its recovery-time statistics), stating
  the actual n it was computed from.

## 5. Pre-collection verification (small, functional, before freezing)

Each check has a pass/fail criterion stated in advance, run against the
corrected implementation before any schedule is frozen:

1. **Warm-up never produces a targeted timing record, within a stated
   bounded window** -- not an unfalsifiable "never": run the corrected
   controller through the warm-up phase alone (no timed ping sent) and
   confirm no record is emitted within a fixed observation window after
   warm-up completes.
2. **The intended packet produces the correct record**: a full trial's
   emitted record identity-matches h1 specifically (every field in A,
   not source alone).
3. **A packet with mismatched identity is rejected**: inject a packet
   that matches destination but not full identity (e.g. correct IPs but
   a different ICMP identifier/sequence) and confirm no record is
   produced for it.
4. **An unexpected rule is detected as a setup deviation**: deliberately
   install a rule outside the warm-up-expected set before the trial
   starts, and confirm the pre-flight check in C rejects the trial as a
   deviation rather than proceeding -- without the check needing to
   claim what that extra rule would or would not have done to the target
   packet.
5. **`dump-flows` field-order independence**: feed the parser sample
   output with fields in a different order than the code writes them in,
   and confirm the per-field check still matches correctly.
6. **No duplicate recording**: a retransmitted or duplicate target
   packet does not produce a second record for the same trial.
7. **Connectivity and monitoring failures land on the correct fields of
   E**, independently -- not collapsed into one "invalid" bucket, and not
   cross-contaminating each other: deliberately force (i) a ping failure
   with a healthy, successfully-confirmed rule, (ii) a confirmation
   timeout with a healthy monitor and no ping attempted yet, and (iii) a
   `dump-flows` tool error, in three separate test runs, and confirm each
   sets only the fields it should (e.g. (i) sets connectivity=failed
   while rule observation=confirmed, demonstrating the two axes vary
   independently rather than forcing one outcome).

Only after all of these pass, with their logs reviewed, is the 30-block
schedule generated and frozen, and only then does official collection
begin.

## 6. What happens to the paper afterward

- Table 4, Table 4b, Figure 5, and every interpretive sentence in
  §6.2.1/§7.2 built on them are regenerated from the new results,
  whichever direction they point -- including if the ordering between
  adapters changes from what the old (now-disqualified) data showed.
- The response letter states this correction and its effect plainly
  (what was wrong, what changed, what the new numbers show), not as a
  wording or presentation fix.
- I3 (the separate four-way-comparison boundary/interpretation problem)
  is handled in parallel as its own measurement-and-text audit -- this
  does not require reopening ONOS/OpenDaylight work, and does not
  require re-running every experiment in the paper, only this one.

## 7. Implementation and verification checkpoint (2026-10-01)

New isolated files: `s56_measurement.py`, `s56_corrected_controller.py`,
`s56_corrected_runner.py`, `test_s56_measurement.py`, and
`analysis/s56_corrected_analysis.py`. Legacy collectors and raw CSVs are unchanged.
C was rebuilt with the existing strict flags into `implementation/build-s56/`.
No change to DAIM C source or ctypes ABI was made.

Local tests cover every identity field, disarmed acceptance, duplicate rejection,
field-order invariance, cross-rule false positives, unexpected rules, ping counts,
and observer outcomes. All five test groups pass. Limited verification v4:
21/21 planned checks pass (seven scenarios x three modes), saved separately.
Earlier diagnostic v1 failed on the Linux interface-name length limit; v2 passed
nine functional checks; v3 exposed an uncaught TimeoutExpired class mismatch in
Os-Ken/eventlet. These records are retained; none is official performance data.
The observer now records exceptions explicitly, including deadline exhaustion.

Implementation refinements supersede ambiguous prose above: `stopped_at_phase`
and a reason distinguish readiness failure from unattempted target/observation;
unexpected parsed flows are setup deviations; observer execution/parse errors
are tool errors. A latency is eligible only when protocol, full event identity,
unique record, ordered timestamps, and full-rule confirmation all pass. Ping
success is independent of timing eligibility. The target-free warm-up window is
200 ms. Linux partial-ping exit 0 with some packets received is a valid partial
service result, not a parser defect; a new pure parser preserves this distinction.

Frozen analysis: per-mode mean/median and 95% percentile bootstrap intervals;
three paired per-block mean/median differences with 20,000 resamples, seed
20261001. Intervals are marginal descriptive estimates, not family-wise tests
of architectural superiority. p95/p99 are descriptive. Missing times are never
imputed; each paired estimate uses common eligible blocks and reports its n.
All 90 scheduled attempts remain in the outcome report. The analysis verifies
identity and full-rule evidence again, and checks each C-stage sum in integer ns.

Official collection is allowed only by the runner's verification gate: all 21
checks must pass and controller/helper/runner/test/library hashes must still match.
The schedule and parameter/source manifest are written before the first attempt.

