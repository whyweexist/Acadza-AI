# Safety policy and threat model

## Trust boundaries

1. Student comments and original HTML are untrusted input, never instructions.
2. Only the `claim` and `reply` agents receive raw student comments. No solver sees them.
3. LLM output is a proposal validated against typed schemas and the closed taxonomy.
4. `safety_gate` is independent of the model. Confidence is calculated from evidence agreement, not the model's claimed probability.
5. A faculty action only records an approved patch proposal. Publishing is a separate integration with explicit privileges.

## Deterministic rules

- `edit.field` must appear in `repairs[repair].fields`. For `auto:false`, automatic patches are prohibited.
- Exact match count must equal one. Equal find/replace is invalid. Patches apply to deep copies; original question snapshots are immutable.
- Spelling must not change digit, symbol or markup tokens. Noise/exam reference is deletion-only. Answer-form is additive.
- Option repair must preserve the raw pre-option stem and produce a unique, nonempty option.
- Stem-data insertion numbers must be present in the source solution; this is necessary, **not sufficient**, proof.
- Answer-key change requires both independent solvers to agree on the new keyed answer; valid actual options or numeric form are required. The separate solution audit must agree or explain disagreement.
- Solution repair must be independently audited and the resulting solution must end at the existing keyed answer.
- No student-comment string is copied directly into an executable edit.
- Question hash and case revision preconditions are mandatory. `auto_apply` needs full gate success and evidence score >=0.85 (>=0.90 for key changes).
- Non-defect results have `no_change` routing and cannot claim an applied patch.

## Known security/operational limitations to address before production rollout

- `ADMIN_REVIEW_TOKEN` is a **shared demo secret**, not SSO. For production use a secure identity provider, institution RBAC, server-side permissions and immutable per-user identity.
- Implement explicit per-tenant and per-question authorization when adding multiple institutes.
- Review API mutation rate limiting should be added at ingress, along with request quotas and operational alerts.
- Model/provider output should be evaluated against real faculty-labeled sets and confidence calibrated statistically before permitting production auto-writes.
- Sanitized HTML supports MathML; image refs must use an allowlisted first-party proxy rather than arbitrary remote URLs.
- Backups must capture SQLite plus WAL consistently and be restore-tested on an isolated instance.
- Never host a persistent writable SQLite database on multiple independent serverless instances or ephemeral volumes.
- No security penetration test or application test has been executed in this requested handoff.
