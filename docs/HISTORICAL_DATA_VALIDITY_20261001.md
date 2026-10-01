# Historical data and corrected experiments

This internal note separates retained historical data from new evidence. The new experiments do not retroactively repair missing packet identities, missing raw ping output, or mismatched measurement boundaries in older datasets. Old CSV/JSON files remain unchanged.

## Packet In timing

The old Section 5.6 controller selected the first packet with the target destination IP, while the driver sent a warm-up packet to that same IP. Its retained records cannot distinguish the warm-up source from the intended target source. `installed` records an attempted call when a destination is known; destination-only `confirmed` does not establish the complete intended rule or packet identity.

The corrected 90-attempt sample uses full packet identity, explicit activation after verified warm-up, a pre-flight flow-table check, full target-rule observation, raw ping/count/return-code evidence and independent outcome axes. Its 21 verification gates precede the sample. All 90 scheduled attempts met the corrected protocol. The resulting statistics are a replacement dataset for the intended claim, not a retrospective repair or a poolable continuation of the old 90 rows.

Until the manuscript and figures are consistently regenerated, the old 2.661 ms mean and 83.45%/94.55% stage shares must not be presented as the corrected results. The new mean values and stage decomposition reside in `experiments/results/network/s56_corrected_official_20261001/statistics.json`.

The corrected source's raw `t_packetout_sent_ns` name denotes the point after `send_msg(PacketOut)` returns, not an observed wire transmission. Stage labels must say PacketOut submission/send-call return. The primary handler-entry-to-full-rule-observation metric and all integer interval values remain unchanged by this interpretation clarification.

## Historical connectivity flags

The original packet-in, load-profile and stage2 collectors use the substring `0% packet loss`, which also occurs in `100% packet loss`. A stored Boolean alone therefore cannot prove full connectivity. The preserved smoke-test raw ping output can be reparsed; datasets retaining only the flag cannot be repaired in that way.

Separate signals require separate interpretations. A successful subprocess exit, a successful socket write, a switch rule observation and successful end-to-end packet delivery are different evidence. Counters must not be used interchangeably. The new service campaign stores packet counts, exit codes and raw output for every probe, but its new successful probes do not prove that old probes succeeded.

The historical collectors are retained for provenance. Their old success predicates must not be used for a new validated collection. The corrected `s56_*` drivers and the separate `r5_service_campaign.py` use the reviewed parser instead.

## Four path benchmark boundaries

Source inspection confirms that the original four-path benchmark is an implementation/configuration experiment with different timing spans. The C adapter CLIs call the switch-adapter interface directly; they do not traverse the DAIM Core or ctypes bridge.

| Historical path | Recorded timing span | Interpretation limit |
| --- | --- | --- |
| DAIM process-per-rule CLI | Parent timer wraps the complete spawned CLI invocation, including its OVS utility call | No Core or ctypes path; not isolated process-spawn cost |
| Direct ovs-ofctl | Parent timer wraps the complete spawned utility invocation | Command duration includes process and tool execution |
| Persistent adapter CLI | Listener is launched before the timer; timer includes setting the OVS controller target and waiting for the listener process | Startup exclusion differs from the two spawned-command paths |
| Direct Os-Ken | Controller reports switch-features-handler entry through Barrier Reply | Internally measured and differently bounded; not the same external command span |

The old observations can describe those explicitly named spans. They cannot isolate Core/ctypes overhead, establish a common rule-installation latency, or provide an architectural ranking across controllers. The corrected Section 5.6 supplies a common handler-entry-to-rule-observed boundary for its three modes. The new four-platform service campaign instead uses a common external probe procedure and explicitly includes differing native application policies; these are two distinct questions.

## Reproduction and publication

The corrected Section 5.6 sample has been added to the local artifact candidate and reanalysed from that copy with byte-identical statistics. Its current manifest was regenerated and verified while the previous manifest was retained for provenance. This does not change the published v1.1.0 tag or DOI snapshot. The additional campaign has also been packaged locally (commit `8adf595`); five derived outputs reproduce byte-for-byte and all 592 current manifest entries verify. Eight unused distributed source files captured by the broad original inventory are explicitly excluded from the public-candidate source export, while the complete private snapshot is retained. A final release still requires consistent manuscript/response references and a separately authorized publication action.

The current manuscript and response letter still require integration and a consistency pass against the corrected datasets. Completing experiments alone does not make those documents submission-ready.
