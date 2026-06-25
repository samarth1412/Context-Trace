# ContextTrace-Bench Error Analysis

- Benchmark: `ContextTrace-Bench`
- Mode: `semantic`
- Case set: `external_case_pack`
- Cases: `200`
- Benchmark misses: `14`
- Label misses: `10`

## Confusion Matrix

| Expected | Predicted | Count |
| --- | --- | ---: |
| `no_failure_detected` | `no_failure_detected` | 110 |
| `contradicted_answer` | `contradicted_answer` | 40 |
| `partial_support` | `partial_support` | 39 |
| `contradicted_answer` | `partial_support` | 3 |
| `no_failure_detected` | `partial_support` | 3 |
| `partial_support` | `contradicted_answer` | 3 |
| `no_failure_detected` | `contradicted_answer` | 1 |
| `unsupported` | `unsupported` | 1 |

## Root-Cause Confusion

| Expected Root | Predicted Root | Count |
| --- | --- | ---: |
| `no_failure_detected` | `no_failure_detected` | 110 |
| `answer_overreach` | `answer_overreach` | 40 |
| `conflicting_contexts` | `conflicting_contexts` | 40 |
| `answer_overreach` | `conflicting_contexts` | 3 |
| `conflicting_contexts` | `answer_overreach` | 3 |
| `no_failure_detected` | `answer_overreach` | 3 |
| `no_failure_detected` | `conflicting_contexts` | 1 |

## False-Positive Labels

| Label | Count |
| --- | ---: |
| `partial_support` | 3 |
| `contradicted_answer` | 1 |

## Cases To Review

- `ragtruth_121`: expected `['contradicted_answer']`, predicted `['partial_support']`, root `conflicting_contexts -> answer_overreach`
  Claim: After serving over seven years in prison, they have been married for 10 years.
  Missing: After serving over seven years in prison, they have been married for 10 years; 10 years
- `ragtruth_730`: expected `['partial_support']`, predicted `['contradicted_answer']`, root `answer_overreach -> conflicting_contexts`
  Claim: A nuclear submarine at a Russian shipyard caught fire during repairs, but there's no danger of radiation or explosion as there's no ammunition or fissile materials on board.
  Conflicting: A nuclear submarine at a Russian shipyard caught fire during repairs, but there's no danger of radiation or explosion as there's no ammunition or fissile materials on board.
- `ragtruth_4211`: expected `['contradicted_answer']`, predicted `['partial_support']`, root `conflicting_contexts -> answer_overreach`
  Claim: However, additional funding from Congress is needed to process more applications and reduce the current 30-day processing time.
  Missing: However, additional funding from Congress is needed to process more applications and reduce the current 30-day processing time
- `ragtruth_7052`: expected `['contradicted_answer']`, predicted `['partial_support']`, root `conflicting_contexts -> answer_overreach`
  Claim: The restaurant has outdoor seating available.
  Missing: The restaurant has outdoor seating available
- `ragtruth_7236`: expected `['partial_support']`, predicted `['contradicted_answer']`, root `answer_overreach -> conflicting_contexts`
  Claim: The restaurant is open from 7:00 AM to 10:30 PM on Mondays and Tuesdays, and from 5:00 PM to 9:30 PM from Wednesday to Sunday.
  Missing: The restaurant is open from 7:00 AM to 10:30 PM on Mondays and Tuesdays, and from 5:00 PM to 9:30 PM from Wednesday to Sunday
  Conflicting: hours
- `ragtruth_9604`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: According to customer reviews, the restaurant offers high-quality ingredients and unique flavor combinations, with a focus on sustainability and locally sourced ingredients.
  Missing: offers high-quality ingredients; offers unique flavor combinations; offers with a focus on sustainability; locally sourced ingredients
- `ragtruth_10072`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Its menu includes sushi, sashimi, and rolls, with prices ranging from $15 to $25 per item.
  Missing: includes with prices ranging from $15 to $25 per item
- `ragtruth_14007`: expected `['partial_support']`, predicted `['contradicted_answer']`, root `answer_overreach -> conflicting_contexts`
  Claim: It is introduced by a relative pronoun (who, whose, him, her, it, that) or a subordinate conjunction (when and where).
  Conflicting: her, him, it
- `ragtruth_15904`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: When a positive voltage is applied to the base, it creates a region around the base where there are more electrons than holes.
  Missing: When a positive voltage is applied to the base, it creates a region around the base where there are more electrons than holes
- `ragtruth_15933`: expected `['no_failure_detected']`, predicted `['contradicted_answer']`, root `no_failure_detected -> conflicting_contexts`
  Claim: Global egalitarianism refers to a concept of global justice that emphasizes the importance of equality among individuals and groups worldwide.
  Missing: Global egalitarianism refers to a concept of global justice that emphasizes the importance of equality among individuals and groups worldwide
