# Accepted: protobuf PYSEC-2026-1805 via mediapipe 0.10.14

## Status

Accepted.

## Context

`visionai.platform.webcam` uses mediapipe's legacy `solutions.hands` API for
offline hand-landmark detection. Newer mediapipe releases (0.10.35 and 1.0.1
were both checked) drop `mediapipe.solutions` from their Windows wheels in
favor of a Tasks API that requires downloading a model file at runtime;
0.10.14 is the newest cp312 Windows wheel confirmed to still ship
`solutions.hands`, keeping hand-landmark detection fully offline.

mediapipe 0.10.14 requires `protobuf<5,>=4.25.3`. Every protobuf 4.x release,
including the latest patch (4.25.9), carries PYSEC-2026-1805: a
denial-of-service vulnerability in `google.protobuf.json_format.ParseDict()`,
where deeply nested `google.protobuf.Any` messages bypass the recursion-depth
limit and exhaust the Python recursion stack. No protobuf release inside
mediapipe's allowed range fixes it; the fix versions (5.29.6, 6.33.5) both
fall outside `<5`.

## Decision

Accept the vulnerable transitive protobuf pin. `visionai` never calls
`google.protobuf.json_format.ParseDict()` or otherwise parses untrusted JSON
into protobuf `Any` messages anywhere in this codebase -- mediapipe uses
protobuf internally only for its own bundled model graph configuration, not
for handling attacker-controlled input. The vulnerable code path is present
in the dependency tree but not reachable from any code this project runs.

`scripts/verify.ps1`'s `pip_audit` check only scopes `requirements/base.txt`
and `requirements/dev.txt` (the same existing scope `requirements/voice.txt`
falls outside of), so this does not currently fail the automated
verification gate. A full-environment `pip-audit` (or any future CI step
that widens scope to `requirements/vision.txt`) will still report it; this
document is the record for why that finding is a known, accepted exception
rather than an unreviewed regression.

## Revisit when

mediapipe ships a release that both keeps (or replaces with an equivalent
offline model) the `solutions.hands` API on Windows/cp312 and allows
protobuf 5+, or a patched protobuf 4.x release becomes available. Re-check
`pip index versions protobuf` and mediapipe's declared `protobuf` requirement
range at that point.
