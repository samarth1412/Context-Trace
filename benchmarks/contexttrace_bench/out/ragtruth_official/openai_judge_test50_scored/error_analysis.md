# ContextTrace-Bench Error Analysis

- Benchmark: `ContextTrace-Bench`
- Mode: `semantic`
- Case set: `external_case_pack`
- Cases: `50`
- Benchmark misses: `50`
- Label misses: `34`

## Confusion Matrix

| Expected | Predicted | Count |
| --- | --- | ---: |
| `no_failure_detected` | `partial_support` | 16 |
| `no_failure_detected` | `no_failure_detected` | 11 |
| `contradicted_answer` | `partial_support` | 5 |
| `contradicted_answer` | `contradicted_answer` | 3 |
| `no_failure_detected` | `contradicted_answer` | 3 |
| `no_failure_detected` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | 2 |
| `no_failure_detected` | `contradicted_answer, insufficient_context, should_have_abstained, unsupported_answer` | 2 |
| `partial_support` | `partial_support` | 2 |
| `contradicted_answer` | `contradicted_answer, insufficient_context` | 1 |
| `no_failure_detected` | `contradicted_answer, partial_support, should_have_abstained, unsupported_answer` | 1 |
| `partial_support` | `contradicted_answer` | 1 |
| `partial_support` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | 1 |
| `partial_support` | `contradicted_answer, partial_support` | 1 |
| `partial_support` | `contradicted_answer, should_have_abstained, unsupported_answer` | 1 |

## Root-Cause Confusion

| Expected Root | Predicted Root | Count |
| --- | --- | ---: |
| `no_failure_detected` | `answer_overreach` | 16 |
| `no_failure_detected` | `no_failure_detected` | 11 |
| `conflicting_contexts` | `answer_overreach` | 5 |
| `conflicting_contexts` | `conflicting_contexts` | 4 |
| `no_failure_detected` | `should_have_abstained` | 4 |
| `no_failure_detected` | `conflicting_contexts` | 3 |
| `answer_overreach` | `answer_overreach` | 2 |
| `answer_overreach` | `conflicting_contexts` | 2 |
| `answer_overreach` | `should_have_abstained` | 2 |
| `no_failure_detected` | `insufficient_context` | 1 |

## False-Positive Labels

| Label | Count |
| --- | ---: |
| `partial_support` | 19 |
| `contradicted_answer` | 8 |
| `should_have_abstained` | 5 |
| `unsupported_answer` | 5 |
| `insufficient_context` | 4 |

## Cases To Review

- `ragtruth_25`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Thomas had sent multiple social media messages expressing support for ISIS.
  Missing: Thomas had sent multiple social media messages expressing support for ISIS
- `ragtruth_27`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Three women have been arrested this week on terror charges, including two in New York who were accused of planning to build an explosive device for attacks in the US.
  Missing: Three women have been arrested this week on terror charges, including two in New York who were accused of planning to build an explosive device for attacks in the US
- `ragtruth_28`: expected `['contradicted_answer']`, predicted `['partial_support']`, root `conflicting_contexts -> answer_overreach`
  Claim: Three women, including Keonna Thomas of Philadelphia, were charged with attempting to join ISIS this week.
  Missing: Three women, including Keonna Thomas of Philadelphia, were charged with attempting to join ISIS this week
- `ragtruth_29`: expected `['contradicted_answer']`, predicted `['partial_support']`, root `conflicting_contexts -> answer_overreach`
  Claim: A 30-year-old Philadelphia woman, Keonna Thomas, was charged with attempting to travel to Syria to join ISIS.
  Missing: A 30-year-old Philadelphia woman, Keonna Thomas, was charged with attempting to travel to Syria to join ISIS
- `ragtruth_43`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: However, it is still uncertain if the ice cream is the source of these infections.
  Missing: However, it is still uncertain if the ice cream is the source of these infections
- `ragtruth_45`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Investigations into the possible connection between the ice cream and the infections are ongoing.
  Missing: Investigations into the possible connection between the ice cream and the infections are ongoing
- `ragtruth_47`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: The Centers for Disease Control and Prevention (CDC) has found a link between the contaminated ice cream and a listeria outbreak at a Kansas hospital, but it is not clear if the ice cream is the source of the infections.
  Missing: The Centers for Disease Control and Prevention (CDC) has found a link between the contaminated ice cream and a listeria outbreak at a Kansas hospital, but it is not clear if the ice cream is the source of the infections
- `ragtruth_55`: expected `['no_failure_detected']`, predicted `['contradicted_answer']`, root `no_failure_detected -> conflicting_contexts`
  Claim: The Rolling Stone article presented as fact, which could potentially be deemed false by the law.
  Missing: The Rolling Stone article presented as fact, which could potentially be deemed false by the law
  Conflicting: The Rolling Stone article presented as fact, which could potentially be deemed false by the law.
- `ragtruth_56`: expected `['no_failure_detected']`, predicted `['contradicted_answer', 'insufficient_context', 'should_have_abstained', 'unsupported_answer']`, root `no_failure_detected -> insufficient_context`
  Claim: Rolling Stone has faced criticism for its reporting and editing processes after a story about a purported gang rape at the University of Virginia was found to contain numerous errors and misrepresentations.
  Missing: Rolling Stone has faced criticism for its reporting and editing processes after a story about a purported gang rape at the University of Virginia was found to contain numerous errors and misrepresentations
- `ragtruth_57`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: The article has been widely criticized for its lack of factual accuracy and for damaging the reputations of innocent parties.
  Missing: The article has been widely criticized for its lack of factual accuracy and for damaging the reputations of innocent parties
- `ragtruth_58`: expected `['partial_support']`, predicted `['contradicted_answer', 'insufficient_context', 'partial_support', 'should_have_abstained', 'unsupported_answer']`, root `answer_overreach -> should_have_abstained`
  Claim: The fraternity members mentioned in the article may be able to sue for defamation.
- `ragtruth_59`: expected `['no_failure_detected']`, predicted `['contradicted_answer', 'insufficient_context', 'should_have_abstained', 'unsupported_answer']`, root `no_failure_detected -> should_have_abstained`
  Claim: The article has been widely criticized for its inaccuracies and defamatory content.
  Missing: The article has been widely criticized for its inaccuracies and defamatory content
- `ragtruth_66`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: The first woman and person of color to serve in the Kentucky State Senate has criticized Rand Paul's presidential campaign for being out of touch with the needs of minority communities.
  Missing: The first woman and person of color to serve in the Kentucky State Senate has criticized Rand Paul's presidential campaign for being out of touch with the needs of minority communities
- `ragtruth_67`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: However, his record and positions on issues like voting rights, civil rights legislation, and minority communities raise concerns.
  Missing: record minority communities raise concerns
- `ragtruth_68`: expected `['partial_support']`, predicted `['contradicted_answer', 'should_have_abstained', 'unsupported_answer']`, root `answer_overreach -> should_have_abstained`
  Claim: She criticized his campaign team's message of inclusion as hype and highlighted his past actions that have undermined the rights of marginalized communities.
  Missing: She criticized his campaign team's message of inclusion as hype and highlighted his past actions that have undermined the rights of marginalized communities
- `ragtruth_69`: expected `['no_failure_detected']`, predicted `['contradicted_answer', 'insufficient_context', 'partial_support', 'should_have_abstained', 'unsupported_answer']`, root `no_failure_detected -> should_have_abstained`
  Claim: However, his record has been criticized for questioning landmark voting rights and civil rights legislation, which has led some to believe that he is out of touch with the mainstream and lacks commitment to minority communities.
  Missing: which has led some to believe that he is out of touch with the mainstream
- `ragtruth_71`: expected `['no_failure_detected']`, predicted `['contradicted_answer', 'partial_support', 'should_have_abstained', 'unsupported_answer']`, root `no_failure_detected -> should_have_abstained`
  Claim: Rand Paul, a Kentucky Senator, has announced his candidacy for President, but his record on civil rights and voting rights has been criticized as being out of touch with the mainstream.
  Missing: voting rights has been criticized as being out of touch with the mainstream
- `ragtruth_121`: expected `['contradicted_answer']`, predicted `['partial_support']`, root `conflicting_contexts -> answer_overreach`
  Claim: After serving over seven years in prison, they have been married for 10 years.
  Missing: After serving over seven years in prison, they have been married for 10 years; 10 years
- `ragtruth_124`: expected `['contradicted_answer']`, predicted `['partial_support']`, root `conflicting_contexts -> answer_overreach`
  Claim: Despite serving time in prison for their sexual relationship when he was a minor, they say they're still happy together.
  Missing: Despite serving time in prison for their sexual relationship when he was a minor, they say they're still happy together
- `ragtruth_125`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: After serving 7 years in prison for their sexual relationship, which began when he have two teen daughters.
  Missing: After serving 7 years in prison for their sexual relationship, which began when he have two teen daughters
- `ragtruth_138`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: No further details of the settlement have been disclosed.
  Missing: No further details of the settlement have been disclosed
- `ragtruth_139`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: This incident is not the first time West has been accused of assault.
  Missing: This incident is not the first time West has been accused of assault
- `ragtruth_141`: expected `['contradicted_answer']`, predicted `['contradicted_answer', 'insufficient_context']`, root `conflicting_contexts -> conflicting_contexts`
  Claim: The settlement includes an apology from West to Ramos.
- `ragtruth_142`: expected `['no_failure_detected']`, predicted `['contradicted_answer', 'insufficient_context', 'partial_support', 'should_have_abstained', 'unsupported_answer']`, root `no_failure_detected -> should_have_abstained`
  Claim: Kanye West settled a lawsuit with a paparazzo he assaulted at LAX in 2013.
  Missing: Kanye West settled a lawsuit with a paparazzo he assaulted at LAX in 2013
- `ragtruth_143`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Kanye West has settled a lawsuit with paparazzo Daniel Ramos, who he assaulted at LAX in 2013.
  Missing: Kanye West has settled a lawsuit with paparazzo Daniel Ramos, who he assaulted at LAX in 2013
