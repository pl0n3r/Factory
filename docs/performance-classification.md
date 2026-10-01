# Performance envelope classification

Factory classifies project-produced Performance v1 evidence through one boundary: performance.classifier.classify_performance_envelope. The adapter validates the envelope and delegates each observation to performance.detector.detect_performance; it does not implement another budget or classification algorithm.

The producer must send version 1, classification_authority factory-performance-v1, classification null, project identity, SHA/release, evidence_ref, observed_at and a bounded observations list. Every observation must match the envelope project, SHA/release and evidence_ref. Duplicate surface+metric identities fail closed.

The CLI scripts/performance-classify.py is offline and deterministic. It reads a contract and an envelope from local files, requires an explicit evaluated-at timestamp, and writes JSON to stdout or an optional local output path. It performs no network access, GitHub calls, production writes, WorkItem creation, Team Compiler execution or remediation.

BRVTAL is the first real producer. Its Home mobile/desktop FCP, LCP and CLS observations resolve against performance/contracts/brvtal.json. DOMContentLoaded and loadEventEnd remain outside that contract and therefore pass through the same detector as PERF_REVIEW with UNKNOWN evidence state. The adapter never invents a budget and never accepts a producer-side classification.

This slice stops at classification. Factory #304 still requires a future real material regression before the loop may create a WorkItem, dispatch professional remediation, record before/after evidence and adopt or revert a new baseline.
