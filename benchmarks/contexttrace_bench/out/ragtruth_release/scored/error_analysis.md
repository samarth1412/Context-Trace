# ContextTrace-Bench Error Analysis

- Benchmark: `ContextTrace-Bench`
- Mode: `semantic`
- Case set: `external_case_pack`
- Cases: `200`
- Benchmark misses: `112`
- Label misses: `111`

## Confusion Matrix

| Expected | Predicted | Count |
| --- | --- | ---: |
| `no_failure_detected` | `partial_support` | 64 |
| `contradicted_answer` | `contradicted_answer` | 32 |
| `partial_support` | `partial_support` | 31 |
| `no_failure_detected` | `no_failure_detected` | 26 |
| `no_failure_detected` | `contradicted_answer` | 22 |
| `partial_support` | `contradicted_answer` | 12 |
| `contradicted_answer` | `partial_support` | 11 |
| `partial_support` | `no_failure_detected` | 1 |
| `unsupported` | `partial_support` | 1 |

## Root-Cause Confusion

| Expected Root | Predicted Root | Count |
| --- | --- | ---: |
| `no_failure_detected` | `answer_overreach` | 64 |
| `answer_overreach` | `answer_overreach` | 32 |
| `conflicting_contexts` | `conflicting_contexts` | 32 |
| `no_failure_detected` | `no_failure_detected` | 26 |
| `no_failure_detected` | `conflicting_contexts` | 22 |
| `answer_overreach` | `conflicting_contexts` | 12 |
| `conflicting_contexts` | `answer_overreach` | 11 |
| `answer_overreach` | `no_failure_detected` | 1 |

## False-Positive Labels

| Label | Count |
| --- | ---: |
| `partial_support` | 64 |
| `contradicted_answer` | 22 |

## Cases To Review

- `ragtruth_58`: expected `['partial_support']`, predicted `['contradicted_answer']`, root `answer_overreach -> conflicting_contexts`
  Claim: The fraternity members mentioned in the article may be able to sue for defamation.
- `ragtruth_59`: expected `['no_failure_detected']`, predicted `['contradicted_answer']`, root `no_failure_detected -> conflicting_contexts`
  Claim: The article has been widely criticized for its inaccuracies and defamatory content.
  Missing: The article has been widely criticized for its inaccuracies and defamatory content
- `ragtruth_334`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Superman: Dawn of Justice" features Spanish subtitles and highlights the controversial nature of Superman, with commentators discussing his power and intentions.
  Missing: Superman: Dawn of Justice" features Spanish subtitles and highlights the controversial nature of Superman, with commentators discussing his power and intentions
- `ragtruth_351`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: The Pope faced a difficult decision during a recent mass in Rome, where he chose to acknowledge the deaths of over 1 million Armenians a century ago, while avoiding using the term "genocide".
  Missing: The Pope faced a difficult decision during a recent mass in Rome, where he chose to acknowledge the deaths of over 1 million Armenians a century ago; avoiding using the term "genocide"
- `ragtruth_355`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: National Park Week will include various activities and events, and people are encouraged to share their experiences using #FindYourPark.
  Missing: include various activities; include events
- `ragtruth_543`: expected `['contradicted_answer']`, predicted `['partial_support']`, root `conflicting_contexts -> answer_overreach`
  Claim: He also described the gruesome scenes he witnessed, including the death of 8-year-old Martin Richard, who was close to one of the bombs.
  Missing: He also described the gruesome scenes he witnessed, including the death of 8-year-old Martin Richard, who was close to one of the bombs
- `ragtruth_586`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Sofia Vergara, actress and star of Modern Family, is in a legal battle with her ex-fiancé Nick Loeb over two frozen embryos they created together.
  Missing: Sofia Vergara, actress and star of Modern Family, is in a legal battle with her ex-fiancé Nick Loeb over two frozen embryos they created together
- `ragtruth_730`: expected `['partial_support']`, predicted `['contradicted_answer']`, root `answer_overreach -> conflicting_contexts`
  Claim: A nuclear submarine at a Russian shipyard caught fire during repairs, but there's no danger of radiation or explosion as there's no ammunition or fissile materials on board.
  Conflicting: A nuclear submarine at a Russian shipyard caught fire during repairs, but there's no danger of radiation or explosion as there's no ammunition or fissile materials on board.
- `ragtruth_878`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: The Centers for Disease Control and Prevention (CDC) has yet to determine the cause of the illness, but two CDC staffers will meet the ship in San Diego on Monday to investigate further.
  Missing: The Centers for Disease Control and Prevention (CDC) has yet to determine the cause of the illness, but two CDC staffers will meet the ship in San Diego on Monday to investigate further
- `ragtruth_906`: expected `['partial_support']`, predicted `['contradicted_answer']`, root `answer_overreach -> conflicting_contexts`
  Claim: The University of Virginia (UVA) is currently under investigation for how it handles sexual assault cases on campus.
- `ragtruth_924`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Jiang aims to help others overcome their fear of rejection, which he believes holds people back from achieving their goals.
  Missing: Jiang aims to help others overcome their fear of rejection, which he believes holds people back from achieving their goals
- `ragtruth_1153`: expected `['no_failure_detected']`, predicted `['contradicted_answer']`, root `no_failure_detected -> conflicting_contexts`
  Claim: Two Delaware boys and their father are in critical condition after becoming sick, possibly from pesticide exposure, during a trip to the U.S.
  Missing: Two Delaware boys and their father are in critical condition after becoming sick, possibly from pesticide exposure, during a trip to the U.S
  Conflicting: Two Delaware boys and their father are in critical condition after becoming sick, possibly from pesticide exposure, during a trip to the U.S
- `ragtruth_1355`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Despite nuclear energy being the largest source of carbon-free energy in the US, the plan assumes the phaseout of nuclear power by 2050.
  Missing: Despite nuclear energy being the largest source of carbon-free energy in the US, the plan assumes the phaseout of nuclear power by 2050
- `ragtruth_1513`: expected `['partial_support']`, predicted `['contradicted_answer']`, root `answer_overreach -> conflicting_contexts`
  Claim: While it is a time for Christians to rejoice, Easter has also acquired peripheral traditions such as the bunny and colorful eggs.
  Missing: While it is a time for Christians to rejoice, Easter has also acquired peripheral traditions such as the bunny and colorful eggs
- `ragtruth_1566`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Lauren Hill, a 19-year-old who fought against brain cancer and whose story inspired many, has passed away.
  Missing: Lauren Hill, a 19-year-old who fought against brain cancer and whose story inspired many, has passed away
- `ragtruth_1648`: expected `['no_failure_detected']`, predicted `['contradicted_answer']`, root `no_failure_detected -> conflicting_contexts`
  Claim: President Barack Obama is in Panama for the Summit of the Americas, hoping to improve ties with Latin American leaders and reverse the US's declining influence in the region.
  Missing: President Barack Obama is in Panama for the Summit of the Americas, hoping to improve ties with Latin American leaders and reverse the US's declining influence in the region
- `ragtruth_1678`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Unicef delivered vital aid to Yemen's capital city of Sanaa despite the ongoing conflict, using a rare window of peace to bring food and supplies to those in need.
  Missing: Unicef delivered vital aid to Yemen's capital city of Sanaa despite the ongoing conflict, using a rare window of peace to bring food and supplies to those in need
- `ragtruth_1683`: expected `['no_failure_detected']`, predicted `['contradicted_answer']`, root `no_failure_detected -> conflicting_contexts`
  Claim: The author notes that while most people consider sexual violence as rape, they also include other forms of harassment such as groping, stalking, and ogling, which are equally intimidating.
  Missing: The author notes that; which are equally intimidating
  Conflicting: The author notes that while most people consider sexual violence as rape, they also include other forms of harassment such as groping, stalking, and ogling, which are equally intimidating.
- `ragtruth_1698`: expected `['contradicted_answer']`, predicted `['partial_support']`, root `conflicting_contexts -> answer_overreach`
  Claim: This has resulted in a rise in numbers registered to climb the northern route to Everest, which has led to concerns amongst Nepali companies that climbers will divert to the Chinese side.
  Missing: This has resulted in a rise in numbers registered to climb the northern route to Everest, which has led to concerns amongst Nepali companies that climbers will divert to the Chinese side
- `ragtruth_1990`: expected `['contradicted_answer']`, predicted `['partial_support']`, root `conflicting_contexts -> answer_overreach`
  Claim: A mother was filmed publicly shaming and physically hitting her son, believed to be involved in the Baltimore riots, while praising him in front of the media.
  Missing: A mother was filmed publicly shaming and physically hitting her son, believed to be involved in the Baltimore riots; praising him in front of the media
- `ragtruth_2136`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Munn, known for her role on "The Newsroom", is set to play mutant superheroine Psylocke.
  Missing: Munn, known for her role on "The Newsroom", is set to play mutant superheroine Psylocke
- `ragtruth_2359`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Indiana has declared a public health emergency in the county and has deployed additional resources, including healthcare volunteers and a needle exchange program.
  Missing: Indiana has declared a public health emergency in the county and has deployed additional resources, including healthcare volunteers and a needle exchange program
- `ragtruth_2469`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: Google's popular app Waze allows users to locate police officers in real-time, raising concerns about the safety of law enforcement officials.
  Missing: allows raising concerns about the safety of law enforcement officials
- `ragtruth_2653`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: There is no mention of a beer-flavored ice cream at this time.
  Missing: There is no mention of a beer-flavored ice cream at this time
- `ragtruth_2675`: expected `['no_failure_detected']`, predicted `['partial_support']`, root `no_failure_detected -> answer_overreach`
  Claim: However, the renewed airstrikes have led to confusion about whether the operation has resumed or if it is a short-term series of strikes.
  Missing: However, the renewed airstrikes have led to confusion about whether the operation has resumed or if it is a short-term series of strikes
