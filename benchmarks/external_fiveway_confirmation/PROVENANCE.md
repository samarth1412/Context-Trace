# Dataset provenance and licenses

The confirmation set contains attributed subsets of three public research
datasets. It does not claim ownership of their source text or annotations.

## WiCE

- Ryo Kamoi, Tanya Goyal, Juan Diego Rodriguez, and Greg Durrett. “WiCE:
  Real-World Entailment for Claims in Wikipedia.” EMNLP 2023.
- Repository: <https://github.com/ryokamoi/wice>
- Pinned revision: `ddeb6c183665e2a20c5f03c5aa07f03888b9870f`
- Source: claim-level `test.jsonl`
- License: WiCE annotations are ODC-BY. The source text is based on Wikipedia
  and websites archived by Common Crawl and remains subject to the upstream
  license statement and Common Crawl terms.

## VitaminC

- Tal Schuster, Adam Fisch, and Regina Barzilay. “Get Your Vitamin C! Robust
  Fact Verification with Contrastive Evidence.” NAACL 2021.
- Repository: <https://github.com/TalSchuster/VitaminC>
- Pinned repository revision: `eb532922b88b199df68ed26afeb58dca5501b52f`
- Source: official `vitaminc.zip`, `test.jsonl`; only `real` `REFUTES` rows.
- License: source Wikipedia terms or CC BY-SA 3.0, as described in the
  repository's `DATA_LICENSE`.

## AmbiEnt

- Alisa Liu, Zhaofeng Wu, Julian Michael, Alane Suhr, Peter West, Alexander
  Koller, Swabha Swayamdipta, Noah A. Smith, and Yejin Choi. “We're Afraid
  Language Models Aren't Modeling Ambiguity.” EMNLP 2023.
- Repository: <https://github.com/alisawuffles/ambient>
- Pinned revision: `1fcb43effda068f3047d46b6f9ff0e50e0ee1c1b`
- Source: `AmbiEnt/test.jsonl`
- License: CC BY 4.0.

Exact source-file hashes and URLs are embedded in `confirmation_cases.json` and
`freeze_manifest.json`. The acquisition command rejects any byte-level drift.
