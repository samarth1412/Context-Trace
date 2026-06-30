# Independent review status

Status: pending. No independent reviewer response files are present.

A controlled three-agent LLM simulation is complete for all 200 RAGTruth and
150 Diag cases. It is a protocol stress test only: RAGTruth Fleiss kappa is
`0.033`, Diag-150 kappa is `0.679`, and all 214 label suggestions remain
unapplied. Simulated output does not change this document's pending status.

Prepared reviewer archives:

- `out/contexttrace-arr-review-diag150.zip`
- `out/contexttrace-arr-review-ragtruth200.zip`

Reviewers must receive only the public packet, instructions, and blank response
template. Expected labels, candidate provenance, private keys, and author audit
notes must remain private. A release becomes publishable only after every
required row is reviewed and the validation workflow reports zero errors and
zero warnings.

Review outputs must be retained exactly as received. Corrections belong in a
separate versioned decision file with a rationale; do not overwrite the raw
response.
