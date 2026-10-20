# RecallCircuit threat model

## Trust boundaries

- Regulator facts: GenVM independently fetches from fixed CPSC domains. Source content is still untrusted DATA and can change. DNS/TLS, regulator availability and the onchain web runtime remain external trust dependencies.
- Validator agreement: independently re-fetches pages, prompts a separate LLM and compares strict structured fields. Multiple models can share biases or stale caches; agreement is not a proof of truth.
- Asset owner: can register self-declared product fields and open cases. Registration does not authenticate manufacturer provenance; a malicious owner can supply false attributes.
- Auditor: must be a distinct consenting address for remedy. This is *role separation*, not automatically a regulator-certified inspection service. Collusion is possible.
- Consumer: ReleaseGuard must be correctly integrated by shipment platforms; the contract cannot physically stop product shipment.

## Attacks and mitigations

| Attack | Current design |
| --- | --- |
| Forged recall website | Prefix-locked HTTPS CPSC / SaferProducts URLs; independently fetched and parsed notice |
| LLM prompt injection in regulator or applicant text | Content JSON-encoded as untrusted DATA, instructions specify never obey content |
| Dishonest leader says CLEAR | Validator independently fetches and independently classifies matching official notice vs asset |
| Partial matching ignores production date | Explicit audit prompt requires model, batch, serial, date and exceptions; UNCERTAIN fail-closed |
| Fake JSON schema / truthy flags | Exact key sets and enumerated finding-reason pair checks; malformed -> unknown or revert |
| Unfinished consensus | Case remains PENDING, APPEAL, or REMEDY and release gate stays false |
| Rename asset after recall | Critical declared attributes are immutable after registration; no public update method |
| Hide recalled component | Graph links cannot be changed after a case is started; nested hold propagates recursively |
| Graph cycles | Reject self/cycle linkage; bounded recursive walk |
| New revision silently clears earlier recall | Only original submitter can propose successor; official ID must remain identical; old case held until successor clearance |
| Owner forges remediation | Requires consenting independent auditor attestation plus validator comparison of regulator remedy against public evidence |
| Arbitrary malicious evidence URL | HTTPS and basic private-network/credential checks; URL alone cannot prove remedy |
| Replay old receipt or decision | Case ID, asset revision, notice ID and digest are bound; latest-final UI reads and case statuses determine current release eligibility |
| Unlimited appeals | At most two appeals per case |
| User accidentally on wrong network | UI checks 61999 before signing, switch/add StudioNet RPC only |

## Remaining attack surface / engineering work

- **Manual notice refresh:** If an official CPSC page changes in place, an original submitter must create and verify a successor notice using the SAME URL. The protocol does not automatically monitor regulator edits and an old clearance may be outdated until the revision is initiated. The stored source digest covers validated notice metadata, not every page byte.
- **No full recall universe:** A product may have an unassessed recall even if its registered cases are clear; do not present release eligibility as universal safety.
- **No manufacturer PKI:** Self-declared model, batch and serial can be dishonest. For production, add verified manufacturer credentials and distinct authority attestations.
- **No physical-world enforcement:** Onchain clearance cannot prove a product was repaired or prohibit a warehouse operator from ignoring the contract.
- **URL trust:** Domain-based allowlisting does not guarantee stable document content, and URL redirects must be assessed by the actual GenVM web runner. Expand defense against redirects and DNS rebinding before production use.
- **Cross-contract support:** ReleaseGuard is an optional consumer source; StudioNet intercontract behavior needs a real finalized integration proof.
- **Dissent handling:** `run_nondet_unsafe` may fail a transaction if validators disagree; the existing held state remains. A future explicit appeal arbitration window could provide higher-level recovery.
- **Graph complexity:** bounded traversal limits protect execution but require tests at the maximum depth and with shared children.
- **Remediation semantics:** Operator-submitted public proof + independent auditor + models is not a reliable certification for life-critical uses without an approved repair-verification authority.
- **Financial impact:** No GEN custody, token settlements or guaranteed fee estimates are implemented. Fee and finality verification remain necessary for real transactions.
