# ContextTrace-Bench Error Analysis

- Benchmark: `ContextTrace-Bench`
- Mode: `semantic`
- Case set: `external_case_pack`
- Cases: `50`
- Benchmark misses: `50`
- Label misses: `32`

## Confusion Matrix

| Expected | Predicted | Count |
| --- | --- | ---: |
| `no_failure_detected` | `no_failure_detected` | 11 |
| `no_failure_detected` | `partial_support` | 10 |
| `no_failure_detected` | `contradicted_answer` | 7 |
| `contradicted_answer` | `partial_support` | 4 |
| `partial_support` | `partial_support` | 4 |
| `contradicted_answer` | `contradicted_answer` | 3 |
| `contradicted_answer` | `contradicted_answer, insufficient_context` | 2 |
| `no_failure_detected` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | 2 |
| `no_failure_detected` | `contradicted_answer, partial_support` | 2 |
| `no_failure_detected` | `contradicted_answer, insufficient_context, unsupported_answer` | 1 |
| `no_failure_detected` | `contradicted_answer, partial_support, should_have_abstained, unsupported_answer` | 1 |
| `no_failure_detected` | `contradicted_answer, should_have_abstained, unsupported_answer` | 1 |
| `partial_support` | `contradicted_answer` | 1 |
| `partial_support` | `contradicted_answer, insufficient_context, should_have_abstained, unsupported_answer` | 1 |

## Root-Cause Confusion

| Expected Root | Predicted Root | Count |
| --- | --- | ---: |
| `no_failure_detected` | `no_failure_detected` | 11 |
| `no_failure_detected` | `answer_overreach` | 10 |
| `no_failure_detected` | `conflicting_contexts` | 9 |
| `conflicting_contexts` | `conflicting_contexts` | 5 |
| `answer_overreach` | `answer_overreach` | 4 |
| `conflicting_contexts` | `answer_overreach` | 4 |
| `no_failure_detected` | `should_have_abstained` | 4 |
| `answer_overreach` | `conflicting_contexts` | 1 |
| `answer_overreach` | `should_have_abstained` | 1 |
| `no_failure_detected` | `insufficient_context` | 1 |

## False-Positive Labels

| Label | Count |
| --- | ---: |
| `partial_support` | 15 |
| `contradicted_answer` | 14 |
| `unsupported_answer` | 5 |
| `should_have_abstained` | 4 |
| `insufficient_context` | 3 |

## Cases To Review

- `ragtruth_25`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Thomas had sent multiple social media messages expressing support for ISIS.
  Missing: Thomas had sent multiple social media messages expressing support for ISIS
- `ragtruth_28`: expected `['contradicted_answer']`, predicted `['partial_support']`, root `conflicting_contexts -> answer_overreach`
  Claim: Three women, including Keonna Thomas of Philadelphia, were charged with attempting to join ISIS this week.
  Missing: Three women, including Keonna Thomas of Philadelphia, were charged with attempting to join ISIS this week
- `ragtruth_29`: expected `['contradicted_answer']`, predicted `['partial_support']`, root `conflicting_contexts -> answer_overreach`
  Claim: A 30-year-old Philadelphia woman, Keonna Thomas, was charged with attempting to travel to Syria to join ISIS.
  Missing: A 30-year-old Philadelphia woman, Keonna Thomas, was charged with attempting to travel to Syria to join ISIS
- `ragtruth_43`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: However, the company has issued a recall for other products.
  Missing: However, the company has issued a recall for other products
- `ragtruth_54`: expected `['no_failure_detected']`, predicted `['contradicted_answer', 'partial_support']`, root `no_failure_detected -> conflicting_contexts`
  Claim: Following the apology, the question has arisen as to whether the University, the Phi Kappa Psi fraternity or any of the other fraternities on campus can sue for defamation.
  Missing: Following the apology, the question has arisen as to whether the University, the Phi Kappa Psi fraternity or any of the other fraternities on campus can sue for defamation
- `ragtruth_55`: expected `['no_failure_detected']`, predicted `['contradicted_answer']`, root `no_failure_detected -> conflicting_contexts`
  Claim: Individual fraternity members are likely considered private individuals rather than public figures, making it easier for them to prove defamation.
  Conflicting: Individual fraternity members are likely considered private individuals rather than public figures, making it easier for them to prove defamation.
- `ragtruth_56`: expected `['no_failure_detected']`, predicted `['contradicted_answer', 'insufficient_context', 'unsupported_answer']`, root `no_failure_detected -> insufficient_context`
  Claim: Rolling Stone has faced criticism for its reporting and editing processes after a story about a purported gang rape at the University of Virginia was found to contain numerous errors and misrepresentations.
  Missing: Rolling Stone has faced criticism for its reporting and editing processes after a story about a purported gang rape at the University of Virginia was found to contain numerous errors and misrepresentations
- `ragtruth_57`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: The article has been widely criticized for its lack of factual accuracy and for damaging the reputations of innocent parties.
  Missing: The article has been widely criticized for its lack of factual accuracy and for damaging the reputations of innocent parties
- `ragtruth_58`: expected `['partial_support']`, predicted `['contradicted_answer', 'insufficient_context', 'should_have_abstained', 'unsupported_answer']`, root `answer_overreach -> should_have_abstained`
  Claim: The fraternity members mentioned in the article may be able to sue for defamation.
- `ragtruth_59`: expected `['no_failure_detected']`, predicted `['contradicted_answer', 'should_have_abstained', 'unsupported_answer']`, root `no_failure_detected -> should_have_abstained`
  Claim: The article has been widely criticized for its inaccuracies and defamatory content.
  Missing: The article has been widely criticized for its inaccuracies and defamatory content
- `ragtruth_66`: expected `['no_failure_detected']`, predicted `['contradicted_answer', 'partial_support']`, root `no_failure_detected -> conflicting_contexts`
  Claim: She states that while Paul has attempted to brand himself as the GOP's minority outreach candidate, his policies do not support this image.
  Conflicting: She states that while Paul has attempted to brand himself as the GOP's minority outreach candidate, his policies do not support this image.
- `ragtruth_67`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: However, his record and positions on issues like voting rights, civil rights legislation, and minority communities raise concerns.
  Missing: record minority communities raise concerns
- `ragtruth_69`: expected `['no_failure_detected']`, predicted `['contradicted_answer', 'insufficient_context', 'partial_support', 'should_have_abstained', 'unsupported_answer']`, root `no_failure_detected -> should_have_abstained`
  Claim: However, his record has been criticized for questioning landmark voting rights and civil rights legislation, which has led some to believe that he is out of touch with the mainstream and lacks commitment to minority communities.
  Missing: which has led some to believe that he is out of touch with the mainstream
- `ragtruth_70`: expected `['no_failure_detected']`, predicted `['contradicted_answer']`, root `no_failure_detected -> conflicting_contexts`
  Claim: He has also shown a lack of cultural competency and disrespected the intelligence of the American people.
  Conflicting: He has also shown a lack of cultural competency and disrespected the intelligence of the American people.
- `ragtruth_71`: expected `['no_failure_detected']`, predicted `['contradicted_answer', 'partial_support', 'should_have_abstained', 'unsupported_answer']`, root `no_failure_detected -> should_have_abstained`
  Claim: Rand Paul, a Kentucky Senator, has announced his candidacy for President, but his record on civil rights and voting rights has been criticized as being out of touch with the mainstream.
  Missing: voting rights has been criticized as being out of touch with the mainstream
- `ragtruth_121`: expected `['contradicted_answer']`, predicted `['contradicted_answer', 'insufficient_context']`, root `conflicting_contexts -> conflicting_contexts`
  Claim: After serving over seven years in prison, they have been married for 10 years.
  Missing: 10 years
  Conflicting: 10
- `ragtruth_124`: expected `['contradicted_answer']`, predicted `['partial_support']`, root `conflicting_contexts -> answer_overreach`
  Claim: Despite serving time in prison for their sexual relationship when he was a minor, they say they're still happy together.
  Missing: Despite serving time in prison for their sexual relationship when he was a minor, they say they're still happy together
- `ragtruth_125`: expected `['no_failure_detected']`, predicted `['contradicted_answer']`, root `no_failure_detected -> conflicting_contexts`
  Claim: After serving 7 years in prison for their sexual relationship, which began when he have two teen daughters.
  Conflicting: 7
- `ragtruth_138`: expected `['no_failure_detected']`, predicted `['contradicted_answer']`, root `no_failure_detected -> conflicting_contexts`
  Claim: Ramos' lawyer, Gloria Allred, has stated that the case has been dismissed as it was "settled to the satisfaction of the parties", adding that "one important aspect of it was an apology by Kanye West to our client, Daniel Ramos.
  Conflicting: Ramos' lawyer, Gloria Allred, has stated that the case has been dismissed as it was "settled to the satisfaction of the parties", adding that "one important aspect of it was an apology by Kanye West to our client, Daniel Ramos.
- `ragtruth_139`: expected `['no_failure_detected']`, predicted `['contradicted_answer']`, root `no_failure_detected -> conflicting_contexts`
  Claim: This incident is not the first time West has been accused of assault.
  Conflicting: This incident is not the first time West has been accused of assault.
- `ragtruth_141`: expected `['contradicted_answer']`, predicted `['contradicted_answer', 'insufficient_context']`, root `conflicting_contexts -> conflicting_contexts`
  Claim: The settlement includes an apology from West to Ramos.
- `ragtruth_142`: expected `['no_failure_detected']`, predicted `['contradicted_answer', 'insufficient_context', 'partial_support', 'should_have_abstained', 'unsupported_answer']`, root `no_failure_detected -> should_have_abstained`
  Claim: Kanye West settled a lawsuit with a paparazzo he assaulted at LAX in 2013.
  Missing: Kanye West settled a lawsuit with a paparazzo he assaulted at LAX in 2013
- `ragtruth_143`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Kanye West has settled a lawsuit with paparazzo Daniel Ramos, who he assaulted at LAX in 2013.
  Missing: Kanye West has settled a lawsuit with paparazzo Daniel Ramos, who he assaulted at LAX in 2013
- `ragtruth_145`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: However, he is now feeling much better.
  Missing: However, he is now feeling much better
- `ragtruth_146`: expected `['contradicted_answer']`, predicted `['partial_support']`, root `conflicting_contexts -> answer_overreach`
  Claim: King, the legendary blues musician, was hospitalized for dehydration caused by his Type II diabetes.
  Missing: King, the legendary blues musician, was hospitalized for dehydration caused by his Type II diabetes
