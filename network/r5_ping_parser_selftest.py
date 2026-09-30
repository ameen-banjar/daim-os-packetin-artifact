#!/usr/bin/env python3
"""Standalone local test of the ping-output parser used by
r5_restart_recovery_feasibility.py -- runs with no VM, no Mininet, no
network access. Imports the parser directly and re-runs the same
self-test the feasibility script runs on every invocation, plus a few
additional edge cases exercised only here."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from r5_restart_recovery_feasibility import parse_ping_output, _self_test_parser  # noqa: E402


def main():
    _self_test_parser()
    print("built-in self-test: PASS")

    # expected_ok=None means "must come back invalid" (a tool-measurement
    # error), not a trustworthy True/False service observation -- the
    # round-2 review tightened this: RC/count disagreement and a missing
    # RC marker are now both invalid, not "valid but not ok".
    extra_cases = [
        ("rc/count agree on failure with errors line", "5 packets transmitted, 0 received, +5 errors, 100% packet loss, time 400ms\r\nRC=1\n", False),
        ("rc says success but counts disagree -- now invalid, not trusted either way", "1 packets transmitted, 0 received, 100% packet loss, time 0ms\r\nRC=0\n", None),
        ("no RC marker at all -- now invalid, not silently trusted from counts alone", "1 packets transmitted, 1 received, 0% packet loss, time 0ms\n", None),
        ("large count partial success exactly half", "10 packets transmitted, 5 received, 50% packet loss, time 900ms\r\nRC=1\n", False),
        ("count=1 received=1 but negative-looking noise around it", "noise noise 1 packets transmitted, 1 received, 0% packet loss, time 0ms noise\r\nRC=0\n", True),
    ]
    failures = []
    for name, text, expected_ok in extra_cases:
        r = parse_ping_output(text)
        if expected_ok is None:
            ok = not r["valid"]
        else:
            ok = r["valid"] and r["ok"] == expected_ok
        status = "PASS" if ok else "FAIL"
        print(f"[{status}] {name}: valid={r['valid']} ok={r['ok']} parse_error={r['parse_error']}")
        if not ok:
            failures.append(name)

    if failures:
        print(f"\n{len(failures)} extra case(s) FAILED: {failures}")
        sys.exit(1)
    print("\nAll extra cases PASS.")


if __name__ == "__main__":
    main()
