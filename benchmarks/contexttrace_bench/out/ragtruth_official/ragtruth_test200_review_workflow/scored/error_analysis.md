# ContextTrace-Bench Error Analysis

- Benchmark: `ContextTrace-Bench`
- Mode: `semantic`
- Case set: `external_case_pack`
- Cases: `200`
- Benchmark misses: `199`
- Label misses: `155`

## Confusion Matrix

| Expected | Predicted | Count |
| --- | --- | ---: |
| `no_failure_detected` | `partial_support` | 65 |
| `partial_support` | `partial_support` | 23 |
| `no_failure_detected` | `no_failure_detected` | 20 |
| `contradicted_answer` | `partial_support` | 18 |
| `contradicted_answer` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | 9 |
| `no_failure_detected` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | 7 |
| `no_failure_detected` | `contradicted_answer, insufficient_context, should_have_abstained, unsupported_answer` | 5 |
| `partial_support` | `insufficient_context, partial_support, should_have_abstained, unsupported_answer` | 5 |
| `partial_support` | `contradicted_answer, insufficient_context, partial_support, should_have_abstained, unsupported_answer` | 4 |
| `contradicted_answer` | `no_failure_detected` | 3 |
| `no_failure_detected` | `contradicted_answer` | 3 |
| `contradicted_answer` | `contradicted_answer` | 2 |
| `contradicted_answer` | `contradicted_answer, insufficient_context` | 2 |
| `contradicted_answer` | `contradicted_answer, insufficient_context, should_have_abstained` | 2 |
| `contradicted_answer` | `contradicted_answer, insufficient_context, should_have_abstained, unsupported_answer` | 2 |
| `contradicted_answer` | `insufficient_context, partial_support, should_have_abstained, unsupported_answer` | 2 |
| `no_failure_detected` | `contradicted_answer, partial_support` | 2 |
| `no_failure_detected` | `contradicted_answer, partial_support, should_have_abstained, unsupported_answer` | 2 |
| `no_failure_detected` | `contradicted_answer, should_have_abstained, unsupported_answer` | 2 |
| `partial_support` | `contradicted_answer, insufficient_context, should_have_abstained` | 2 |
| `partial_support` | `contradicted_answer, insufficient_context, should_have_abstained, unsupported_answer` | 2 |
| `partial_support` | `no_failure_detected` | 2 |
| `contradicted_answer` | `contradicted_answer, insufficient_context, partial_support, unsupported_answer` | 1 |
| `contradicted_answer` | `contradicted_answer, unsupported_answer` | 1 |
| `contradicted_answer` | `should_have_abstained, unsupported_answer` | 1 |
| `no_failure_detected` | `contradicted_answer, insufficient_context` | 1 |
| `no_failure_detected` | `contradicted_answer, insufficient_context, should_have_abstained` | 1 |
| `no_failure_detected` | `contradicted_answer, unsupported_answer` | 1 |
| `no_failure_detected` | `insufficient_context, partial_support, should_have_abstained` | 1 |
| `no_failure_detected` | `insufficient_context, partial_support, should_have_abstained, unsupported_answer` | 1 |
| `no_failure_detected` | `should_have_abstained, unsupported_answer` | 1 |
| `partial_support` | `contradicted_answer` | 1 |
| `partial_support` | `contradicted_answer, insufficient_context, partial_support, unsupported_answer` | 1 |
| `partial_support` | `contradicted_answer, partial_support, unsupported_answer` | 1 |
| `partial_support` | `contradicted_answer, should_have_abstained, unsupported_answer` | 1 |
| `partial_support` | `insufficient_context, should_have_abstained, unsupported_answer` | 1 |
| `partial_support` | `partial_support, should_have_abstained, unsupported_answer` | 1 |
| `unsupported` | `partial_support` | 1 |

## Root-Cause Confusion

| Expected Root | Predicted Root | Count |
| --- | --- | ---: |
| `no_failure_detected` | `answer_overreach` | 65 |
| `answer_overreach` | `answer_overreach` | 25 |
| `no_failure_detected` | `no_failure_detected` | 20 |
| `conflicting_contexts` | `answer_overreach` | 19 |
| `answer_overreach` | `should_have_abstained` | 12 |
| `conflicting_contexts` | `should_have_abstained` | 12 |
| `no_failure_detected` | `should_have_abstained` | 12 |
| `no_failure_detected` | `conflicting_contexts` | 11 |
| `conflicting_contexts` | `conflicting_contexts` | 6 |
| `no_failure_detected` | `insufficient_context` | 4 |
| `answer_overreach` | `conflicting_contexts` | 3 |
| `conflicting_contexts` | `no_failure_detected` | 3 |
| `answer_overreach` | `insufficient_context` | 2 |
| `answer_overreach` | `no_failure_detected` | 2 |
| `conflicting_contexts` | `insufficient_context` | 2 |
| `answer_overreach` | `retrieval_miss` | 1 |
| `conflicting_contexts` | `retrieval_miss` | 1 |

## False-Positive Labels

| Label | Count |
| --- | ---: |
| `partial_support` | 78 |
| `contradicted_answer` | 24 |
| `should_have_abstained` | 20 |
| `unsupported_answer` | 19 |
| `insufficient_context` | 16 |

## Cases To Review

- `ragtruth_58`: expected `['partial_support']`, predicted `['contradicted_answer', 'insufficient_context', 'should_have_abstained', 'unsupported_answer']`, root `answer_overreach -> should_have_abstained`
  Claim: The fraternity members mentioned in the article may be able to sue for defamation.
- `ragtruth_59`: expected `['no_failure_detected']`, predicted `['contradicted_answer', 'should_have_abstained', 'unsupported_answer']`, root `no_failure_detected -> should_have_abstained`
  Claim: The article has been widely criticized for its inaccuracies and defamatory content.
  Missing: The article has been widely criticized for its inaccuracies and defamatory content
- `ragtruth_121`: expected `['contradicted_answer']`, predicted `['contradicted_answer', 'insufficient_context']`, root `conflicting_contexts -> conflicting_contexts`
  Claim: After serving over seven years in prison, they have been married for 10 years.
  Missing: 10 years
  Conflicting: 10
- `ragtruth_331`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: The trailer features footage of Superman and Batman facing off, along with overlapping commentary from various voices.
  Missing: The trailer features footage of Superman and Batman facing off, along with overlapping commentary from various voices
- `ragtruth_332`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: The trailer showed footage of Superman and included comments from various people about the superheroes.
  Missing: The trailer showed footage of Superman and included comments from various people about the superheroes
- `ragtruth_334`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Superman: Dawn of Justice" features Spanish subtitles and highlights the controversial nature of Superman, with commentators discussing his power and intentions.
  Missing: Superman: Dawn of Justice" features Spanish subtitles and highlights the controversial nature of Superman, with commentators discussing his power and intentions
- `ragtruth_351`: expected `['no_failure_detected']`, predicted `['contradicted_answer', 'insufficient_context', 'should_have_abstained', 'unsupported_answer']`, root `no_failure_detected -> should_have_abstained`
  Claim: The Pope faced a difficult decision during a recent mass in Rome, where he chose to acknowledge the deaths of over 1 million Armenians a century ago, while avoiding using the term "genocide".
  Missing: The Pope faced a difficult decision during a recent mass in Rome, where he chose to acknowledge the deaths of over 1 million Armenians a century ago, while avoiding using the term "genocide"
- `ragtruth_355`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: National Park Week will include various activities and events, and people are encouraged to share their experiences using #FindYourPark.
  Missing: include various activities; include events
- `ragtruth_543`: expected `['contradicted_answer']`, predicted `['partial_support']`, root `conflicting_contexts -> answer_overreach`
  Claim: He also described the gruesome scenes he witnessed, including the death of 8-year-old Martin Richard, who was close to one of the bombs.
  Missing: He also described the gruesome scenes he witnessed, including the death of 8-year-old Martin Richard, who was close to one of the bombs
- `ragtruth_586`: expected `['no_failure_detected']`, predicted `['contradicted_answer', 'insufficient_context']`, root `no_failure_detected -> conflicting_contexts`
  Claim: Sofia Vergara, actress and star of Modern Family, is in a legal battle with her ex-fiancé Nick Loeb over two frozen embryos they created together.
  Missing: Sofia Vergara, actress and star of Modern Family, is in a legal battle with her ex-fiancé Nick Loeb over two frozen embryos they created together
- `ragtruth_656`: expected `['contradicted_answer']`, predicted `['contradicted_answer', 'insufficient_context', 'should_have_abstained', 'unsupported_answer']`, root `conflicting_contexts -> should_have_abstained`
  Claim: he was aboard a boat when he noticed a signal for help.
  Missing: he was aboard a boat when he noticed a signal for help
- `ragtruth_730`: expected `['partial_support']`, predicted `['contradicted_answer', 'insufficient_context', 'should_have_abstained']`, root `answer_overreach -> conflicting_contexts`
  Claim: Here's the summary within 42 words: A nuclear submarine at a Russian shipyard caught fire during repairs, but there's no danger of radiation or explosion as there's no ammunition or fissile materials on board.
  Missing: Here's the summary within 42 words: A nuclear submarine at a Russian shipyard caught fire during repairs, but there's no danger of radiation or explosion as there's no ammunition or fissile materials on board
- `ragtruth_835`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: During a routine traffic stop, state troopers detected the smell of marijuana coming from Nelly's private bus.
  Missing: During a routine traffic stop, state troopers detected the smell of marijuana coming from Nelly's private bus
- `ragtruth_838`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Here's the summary in 65 words: Nelly was arrested on drug charges in Tennessee after a state trooper smelled marijuana coming from his bus.
  Missing: Here's the summary in 65 words: Nelly was arrested on drug charges in Tennessee after a state trooper smelled marijuana coming from his bus
- `ragtruth_878`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: The Centers for Disease Control and Prevention (CDC) has yet to determine the cause of the illness, but two CDC staffers will meet the ship in San Diego on Monday to investigate further.
  Missing: The Centers for Disease Control and Prevention (CDC) has yet to determine the cause of the illness, but two CDC staffers will meet the ship in San Diego on Monday to investigate further
- `ragtruth_885`: expected `['partial_support']`, predicted `['insufficient_context', 'should_have_abstained', 'unsupported_answer']`, root `answer_overreach -> should_have_abstained`
  Claim: Here is a summary of the article in 121 words: Graffiti left behind by World War I soldiers has been discovered in a French chalk quarry, including the names and ranks of nearly 2,000 soldiers.
  Missing: Here is a summary of the article in 121 words: Graffiti left behind by World War I soldiers has been discovered in a French chalk quarry, including the names and ranks of nearly 2,000 soldiers
- `ragtruth_906`: expected `['partial_support']`, predicted `['contradicted_answer']`, root `answer_overreach -> conflicting_contexts`
  Claim: The University of Virginia (UVA) is currently under investigation for how it handles sexual assault cases on campus.
- `ragtruth_924`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Jiang aims to help others overcome their fear of rejection, which he believes holds people back from achieving their goals.
  Missing: Jiang aims to help others overcome their fear of rejection, which he believes holds people back from achieving their goals
- `ragtruth_1153`: expected `['no_failure_detected']`, predicted `['contradicted_answer']`, root `no_failure_detected -> conflicting_contexts`
  Claim: Two Delaware boys and their father are in critical condition after becoming sick, possibly from pesticide exposure, during a trip to the U.S.
  Missing: Two Delaware boys and their father are in critical condition after becoming sick, possibly from pesticide exposure, during a trip to the U.S
  Conflicting: Two Delaware boys and their father are in critical condition after becoming sick, possibly from pesticide exposure, during a trip to the U.S
- `ragtruth_1157`: expected `['contradicted_answer']`, predicted `['contradicted_answer', 'insufficient_context', 'should_have_abstained']`, root `conflicting_contexts -> insufficient_context`
  Claim: Two boys from Delaware and their father are in critical condition, and their mother is undergoing occupational therapy, after falling ill during a trip to the US Virgin Islands.
  Missing: Two boys from Delaware and their father are in critical condition, and their mother is undergoing occupational therapy, after falling ill during a trip to the US Virgin Islands
  Conflicting: Two boys from Delaware and their father are in critical condition, and their mother is undergoing occupational therapy, after falling ill during a trip to the US Virgin Islands
- `ragtruth_1355`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Despite nuclear energy being the largest source of carbon-free energy in the US, the plan assumes the phaseout of nuclear power by 2050.
  Missing: Despite nuclear energy being the largest source of carbon-free energy in the US, the plan assumes the phaseout of nuclear power by 2050
- `ragtruth_1513`: expected `['partial_support']`, predicted `['contradicted_answer', 'partial_support', 'unsupported_answer']`, root `answer_overreach -> conflicting_contexts`
  Claim: While it is a time for Christians to rejoice, Easter has also acquired peripheral traditions such as the bunny and colorful eggs.
  Missing: While it is a time for Christians to rejoice, Easter has also acquired peripheral traditions such as the bunny and colorful eggs
- `ragtruth_1566`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Lauren Hill, a 19-year-old who fought against brain cancer and whose story inspired many, has passed away.
  Missing: Lauren Hill, a 19-year-old who fought against brain cancer and whose story inspired many, has passed away
- `ragtruth_1648`: expected `['no_failure_detected']`, predicted `['contradicted_answer', 'insufficient_context', 'should_have_abstained', 'unsupported_answer']`, root `no_failure_detected -> insufficient_context`
  Claim: Here's the summary within 200 words: President Barack Obama is in Panama for the Summit of the Americas, hoping to improve ties with Latin American leaders and reverse the US's declining influence in the region.
  Missing: Here's the summary within 200 words: President Barack Obama is in Panama for the Summit of the Americas, hoping to improve ties with Latin American leaders and reverse the US's declining influence in the region
- `ragtruth_1678`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Here's the summary in 106 words: Unicef delivered vital aid to Yemen's capital city of Sanaa despite the ongoing conflict, using a rare window of peace to bring food and supplies to those in need.
  Missing: Here's the summary in 106 words: Unicef delivered vital aid to Yemen's capital city of Sanaa despite the ongoing conflict, using a rare window of peace to bring food and supplies to those in need
