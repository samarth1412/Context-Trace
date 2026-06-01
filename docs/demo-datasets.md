# Demo Datasets

ContextTrace ships synthetic local demo datasets so the CLI works immediately after install.

Datasets:

- `refund_policy`
- `employee_handbook`
- `ai_paper_qa`

Each dataset includes:

```text
datasets/demo/<name>/
  documents/
  questions.json
  expected_answers.json
  expected_sources.json
  README.md
```

Question types include answerable, unanswerable, multi-hop, citation-sensitive, conflicting evidence, and edge cases.

Run a demo:

```bash
contexttrace init
contexttrace demo --dataset refund_policy
contexttrace report --last --open
```

The demo runner intentionally creates a mix of good and bad answers so reports show meaningful failures:

- `citation_mismatch`
- `unsupported_answer`
- `retrieval_miss`
- `should_have_abstained`
- `conflicting_sources`

The data is synthetic and safe to use in public screenshots, docs, and CI examples.
