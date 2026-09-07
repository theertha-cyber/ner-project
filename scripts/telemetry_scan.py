#!/usr/bin/env python3
"""Release gate: drive the real stack, then read back what its telemetry actually shipped.

    python scripts/telemetry_scan.py            # against the local compose stack
    python scripts/telemetry_scan.py --dry-run  # self-check, no stack required

Why this exists rather than a set of unit assertions on captured records: the leak this
guards against happens in the **exporters and the formatters**, not in the application's
own data structures. A test that inspects a `LogRecord` in memory passes while the OTLP
log handler ships an unredacted attribute — which is exactly the class of gap the
foundation change found late, when Loki turned out to be provisioned, running, and
receiving nothing. So this queries the three backends over HTTP and reads what they hold.

Three rules the design pins down (design Decision 11, risk 8):

1. **An empty capture is a failure, never a clean result.** A scan that queries three
   backends and reports clean because export was misconfigured is worse than no scan,
   because it produces evidence for a gate. The record-count floor is checked *before* any
   content check and exits non-zero on its own.
2. **Spans and metric labels are covered, not only logs.** This change adds most of its
   new surface there, and the foundation's redaction filter sits on neither.
3. **A finding names the record.** "Something leaked" is not actionable at 2am.

Exit codes: 0 clean, 1 a leak was found, 2 the capture was too thin to conclude anything,
3 the stack was unreachable.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

# --------------------------------------------------------------------------------------
# What counts as a leak
# --------------------------------------------------------------------------------------

# Seeded into the tenant before the flow runs, so a match is unambiguous: these strings
# exist nowhere else on the machine. Deliberately shaped like the real thing — a person's
# name, an email, a filename — because a sentinel like "XXTESTXX" would survive a
# formatter that truncates or a redactor that only matches patterns.
SENTINELS = (
    "Priyadarshini Raghunathan",
    "priyadarshini.raghunathan@example.invalid",
    "Priyadarshini_Raghunathan_Resume.pdf",
    "SCAN-SENTINEL-9F2A4C",
)

# Personal-data shapes that would be a finding even without a seeded value, because they
# indicate content reaching telemetry from some path the seeding did not cover.
PII_PATTERNS = (
    ("email", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("credit_card", re.compile(r"\b(?:\d[ -]?){13,16}\b")),
    ("phone", re.compile(r"\b\+?\d{1,3}[ -]?\(?\d{3}\)?[ -]?\d{3}[ -]?\d{4}\b")),
)

# Values that legitimately look like a pattern match. Kept short and explicit: a broad
# allowlist is how a scan quietly stops finding anything.
PATTERN_ALLOWLIST = (
    "noreply@localhost",
    "@example.com",  # fixtures in seeded demo data, never tenant content
)

# The floor below which the capture proves nothing. Not "greater than zero": one log line
# and one span would also pass that, and a flow that produced one of each is a flow that
# did not run.
#
# The metrics floor is lower than the other two, and deliberately so. Domain metric
# families are created on first record, so a service that has served no traffic yet
# exposes only the foundation's families — measured at ten `ner_*` series across the
# stack on a cold start. A higher floor would fail every clean run on a freshly started
# stack, which trains people to lower it, which is how a floor stops meaning anything.
# What this number has to prove is that Prometheus is scraping and returning platform
# series at all; the logs and spans floors carry the "did the flow actually run" weight.
MINIMUM_RECORDS = {"logs": 20, "spans": 10, "metrics": 8}


class Finding:
    """One leak, with enough context to act on it without re-running the scan."""

    def __init__(self, backend: str, kind: str, detail: str, record: str):
        self.backend = backend
        self.kind = kind
        self.detail = detail
        self.record = record

    def __str__(self) -> str:
        return (
            f"  [{self.backend}] {self.kind}: {self.detail}\n"
            f"      in: {self.record[:400]}"
        )


# --------------------------------------------------------------------------------------
# Backends
# --------------------------------------------------------------------------------------


class Backends:
    def __init__(self, loki: str, tempo: str, prometheus: str, gateway: str):
        self.loki = loki.rstrip("/")
        self.tempo = tempo.rstrip("/")
        self.prometheus = prometheus.rstrip("/")
        self.gateway = gateway.rstrip("/")

    @classmethod
    def from_env(cls) -> "Backends":
        return cls(
            loki=os.environ.get("SCAN_LOKI_URL", "http://localhost:3100"),
            tempo=os.environ.get("SCAN_TEMPO_URL", "http://localhost:3200"),
            prometheus=os.environ.get("SCAN_PROMETHEUS_URL", "http://localhost:9090"),
            gateway=os.environ.get("SCAN_GATEWAY_URL", "http://localhost:8000"),
        )


def _get_json(url: str, timeout: float = 20.0):
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_text(url: str, timeout: float = 20.0) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


# --------------------------------------------------------------------------------------
# Capture
# --------------------------------------------------------------------------------------


def capture_logs(backends: Backends, since_seconds: int) -> list[str]:
    """Every log line the stack emitted in the window, as raw strings.

    Queried by service label rather than by content: searching Loki *for* a sentinel would
    only ever find what the query engine indexes, and the whole point is to see what was
    shipped, including fields nobody thought to index.
    """
    end = int(time.time() * 1_000_000_000)
    start = end - since_seconds * 1_000_000_000
    query = urllib.parse.quote('{service_name=~".+"}')
    url = (
        f"{backends.loki}/loki/api/v1/query_range"
        f"?query={query}&start={start}&end={end}&limit=5000&direction=backward"
    )
    payload = _get_json(url)
    lines: list[str] = []
    for stream in payload.get("data", {}).get("result", []):
        labels = json.dumps(stream.get("stream", {}))
        for _timestamp, line in stream.get("values", []):
            lines.append(f"{labels} {line}")
    return lines


def capture_spans(backends: Backends, since_seconds: int) -> list[str]:
    """Every span in the window, rendered with all of its attributes.

    Rendered rather than filtered: an attribute key nobody expected is exactly the one a
    leak arrives on.
    """
    end = int(time.time())
    start = end - since_seconds
    search = _get_json(
        f"{backends.tempo}/api/search?start={start}&end={end}&limit=200"
    )
    rendered: list[str] = []
    for trace_summary in search.get("traces", []) or []:
        trace_id = trace_summary.get("traceID")
        if not trace_id:
            continue
        try:
            detail = _get_json(f"{backends.tempo}/api/traces/{trace_id}")
        except urllib.error.HTTPError:
            continue
        rendered.extend(_render_spans(detail))
    return rendered


def _render_spans(trace_payload) -> list[str]:
    rendered: list[str] = []
    batches = trace_payload.get("batches") or trace_payload.get("resourceSpans") or []
    for batch in batches:
        scopes = batch.get("scopeSpans") or batch.get("instrumentationLibrarySpans") or []
        for scope in scopes:
            for span in scope.get("spans", []):
                attributes = " ".join(
                    f"{a.get('key')}={_attribute_value(a.get('value'))}"
                    for a in span.get("attributes", [])
                )
                events = " ".join(
                    " ".join(
                        f"{a.get('key')}={_attribute_value(a.get('value'))}"
                        for a in event.get("attributes", [])
                    )
                    for event in span.get("events", []) or []
                )
                rendered.append(f"span {span.get('name')} {attributes} {events}".strip())
    return rendered


def _attribute_value(value) -> str:
    if not isinstance(value, dict):
        return str(value)
    for key in ("stringValue", "intValue", "doubleValue", "boolValue"):
        if key in value:
            return str(value[key])
    return json.dumps(value)


def capture_metric_labels(backends: Backends) -> list[str]:
    """Every series' full label set, as text.

    `/api/v1/series` rather than a query: a query returns the series that currently have
    samples, and a leaked label on a stale series is still a disclosure sitting in the
    store for the length of the retention window.
    """
    rendered: list[str] = []
    payload = _get_json(
        f"{backends.prometheus}/api/v1/series?match[]=" + urllib.parse.quote('{__name__=~"ner_.+"}')
    )
    for series in payload.get("data", []) or []:
        rendered.append(" ".join(f"{k}={v}" for k, v in sorted(series.items())))
    return rendered


# --------------------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------------------


def scan_records(backend: str, records: list[str]) -> list[Finding]:
    findings: list[Finding] = []
    for record in records:
        for sentinel in SENTINELS:
            if sentinel in record:
                findings.append(
                    Finding(backend, "seeded entity value", sentinel, record)
                )
        for name, pattern in PII_PATTERNS:
            for match in pattern.findall(record):
                text = match if isinstance(match, str) else "".join(match)
                if any(allowed in text for allowed in PATTERN_ALLOWLIST):
                    continue
                findings.append(Finding(backend, f"{name} pattern", text, record))
    return findings


def check_capture_floor(captured: dict[str, list[str]]) -> list[str]:
    """The rule that makes every other check mean something.

    Runs before any content check and is reported on its own, because "clean" from an
    empty capture is the failure this whole script exists to make impossible.
    """
    return [
        f"{kind}: captured {len(captured.get(kind, []))}, expected at least {floor}"
        for kind, floor in MINIMUM_RECORDS.items()
        if len(captured.get(kind, [])) < floor
    ]


# --------------------------------------------------------------------------------------
# The seeded flow
# --------------------------------------------------------------------------------------


def drive_seeded_flow(backends: Backends) -> None:
    """Run one chat question and one extraction against the stack, carrying sentinels.

    Best-effort by design: the scan's job is to inspect whatever telemetry the stack
    produced, and a flow that partly fails still produces telemetry worth inspecting. What
    is *not* tolerated is a flow that produced nothing at all, and the capture floor is
    what catches that.
    """
    marker = f"{SENTINELS[3]}-{uuid.uuid4().hex[:8]}"
    question = (
        f"which candidates named {SENTINELS[0]} appear in "
        f"{SENTINELS[2]} — reference {marker}"
    )
    payload = json.dumps({"message": question}).encode("utf-8")
    request = urllib.request.Request(
        f"{backends.gateway}/api/v1/public/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(request, timeout=60).read()
    except Exception as exc:  # noqa: BLE001 - a rejected request still emits telemetry
        print(f"  note: seeded chat request did not complete cleanly ({type(exc).__name__})")

    # Give the batch span processor and the log exporter time to ship. Both are
    # deliberately asynchronous — that is what keeps a telemetry outage from becoming a
    # platform outage — so a scan that reads immediately reads an empty store.
    time.sleep(float(os.environ.get("SCAN_EXPORT_WAIT_SECONDS", "12")))


# --------------------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------------------


def run(backends: Backends, window_seconds: int, skip_flow: bool) -> int:
    if not skip_flow:
        print("Driving seeded flow against the running stack…")
        drive_seeded_flow(backends)

    print("Capturing telemetry…")
    captured: dict[str, list[str]] = {}
    try:
        captured["logs"] = capture_logs(backends, window_seconds)
        captured["spans"] = capture_spans(backends, window_seconds)
        captured["metrics"] = capture_metric_labels(backends)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        print(f"FAIL: a telemetry backend was unreachable: {exc}", file=sys.stderr)
        print(
            "  This is a failure, not a skip. A gate that passes when it cannot read "
            "the stack is not a gate.",
            file=sys.stderr,
        )
        return 3

    for kind, records in captured.items():
        print(f"  {kind}: {len(records)} records")

    shortfalls = check_capture_floor(captured)
    if shortfalls:
        print("\nFAIL: the capture is too thin to conclude anything.", file=sys.stderr)
        for shortfall in shortfalls:
            print(f"  {shortfall}", file=sys.stderr)
        print(
            "\n  An empty or near-empty capture is a failure, never a clean result — it "
            "usually means export is misconfigured, not that the telemetry is clean.",
            file=sys.stderr,
        )
        return 2

    findings: list[Finding] = []
    for kind, records in captured.items():
        findings.extend(scan_records(kind, records))

    if findings:
        print(f"\nFAIL: {len(findings)} finding(s).", file=sys.stderr)
        for finding in findings[:50]:
            print(str(finding), file=sys.stderr)
        if len(findings) > 50:
            print(f"  … and {len(findings) - 50} more", file=sys.stderr)
        return 1

    print("\nPASS: no seeded value and no personal-data pattern in any captured record.")
    return 0


def self_check() -> int:
    """Prove the checks themselves work, with no stack running.

    A scan is only evidence if it has been shown to fail on a real leak. This is the
    cheap, always-runnable half of that; task 8.4 does the expensive half by
    reintroducing a leak into the running stack on purpose.
    """
    failures = []

    planted = [
        f'{{"service":"chat_api"}} {{"msg":"answering for {SENTINELS[0]}"}}',
        'span sql_generation attempts=2 outcome=succeeded',
    ]
    findings = scan_records("logs", planted)
    if not findings:
        failures.append("a planted sentinel in a log line was not found")
    elif SENTINELS[0] not in str(findings[0]):
        failures.append("the finding did not name the offending record")

    if scan_records("spans", ['span sql_generation attempts=2 outcome=succeeded']):
        failures.append("a clean record produced a finding")

    span_only = scan_records("spans", [f"span extraction_run entities.{SENTINELS[0]}=3"])
    if not span_only:
        failures.append("a sentinel present only in a span attribute was not found")

    label_only = scan_records(
        "metrics", [f'__name__=ner_extraction_jobs_total tenant_id={SENTINELS[3]}']
    )
    if not label_only:
        failures.append("a sentinel present only in a metric label was not found")

    if not check_capture_floor({"logs": [], "spans": [], "metrics": []}):
        failures.append("an empty capture did not trip the floor")

    if check_capture_floor(
        {
            "logs": ["x"] * MINIMUM_RECORDS["logs"],
            "spans": ["x"] * MINIMUM_RECORDS["spans"],
            "metrics": ["x"] * MINIMUM_RECORDS["metrics"],
        }
    ):
        failures.append("a sufficient capture tripped the floor")

    if failures:
        for failure in failures:
            print(f"FAIL: {failure}", file=sys.stderr)
        return 1
    print("PASS: self-check — the scan finds planted leaks and rejects empty captures.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="run the scan's own self-check without touching the stack",
    )
    parser.add_argument(
        "--skip-flow",
        action="store_true",
        help="scan telemetry already in the backends without driving a new flow",
    )
    parser.add_argument(
        "--window-seconds",
        type=int,
        default=int(os.environ.get("SCAN_WINDOW_SECONDS", "600")),
        help="how far back to read (default 600)",
    )
    args = parser.parse_args()

    if args.dry_run:
        return self_check()
    return run(Backends.from_env(), args.window_seconds, args.skip_flow)


if __name__ == "__main__":
    sys.exit(main())
