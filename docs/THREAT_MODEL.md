# RecallCircuit threat model

| Risk | Existing boundary | Production hardening still needed |
|---|---|---|
| Fake government notice | Explicitly *not authenticated*; gate conservatively fails closed | Fetch official allowlisted authority endpoints; prove content/version provenance via validators |
| Malicious notice spam | All active notices block unknown matches | Source allowlisting, authenticated publisher set, scoped challenge/retirement controls |
| Leader lies about recall scope | Validators re-evaluate substantive scope and compare critical outcome | Adversarial Direct Mode tests; establish real API semantics |
| Groupthink | Validator agreement is not truth | Source citations, corroboration, appeal review, hold-on-uncertainty |
| Prompt injection | Untrusted notice/product data JSON-encoded and flagged as data | Red-team tests for hostile notices and remedies |
| Graph cycle | Bounded DFS rejects self-references, duplicates and cycles | Model worst-case gas/GenVM cost; indexed closure if needed |
| Stale product identity | Parent links increment revision, earlier verdicts fail gate | Authenticated product manufacturing provenance; freezing identity |
| Source revision | Superseded notice deactivated, new notice needs new evaluation | Notice revision indexing and signed source snapshots |
| Remedy fraud | Model adjudication requested; default uncertain | Signed shop/vendor attestation, serial binding, evidence authenticity |
| Race/challenge | Active unresolved appeal blocks release | Direct Mode and live interleaving tests |
| Storage scan DoS | Hard global limits | Indexed assessments, pagination, benchmark worst case |
| Misuse as legal safety certification | Explicit disclaimers, notice-scoped interface | Independent external compliance review |
