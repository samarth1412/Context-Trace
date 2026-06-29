# ARES-NQ-example External Dataset Review Packet

- Generated at: `2026-06-29T00:10:20+00:00`
- Review rows: `200`

## Reviewer Instructions

Inspect each query, answer, source context, and expected label. Mark `review_status` as `reviewed`, `accepted`, or `approved` only after direct inspection.

Set `context_fair`, `label_correct`, and `root_cause_correct` to true when the row is usable as-is. Use corrected fields when the adapted label, root cause, evidence span, or verdict counts need changes.

For source-span claims, keep only minimal source text in `corrected_expected_evidence_spans` or leave the existing spans if they are already minimal.

## 1. `ares_nq_example_8111631832195028942`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> what is the biggest determinant of climate in venezuela

Answer:

> 1972

Contexts:

- Context `ares_doc_8111631832195028942`:

```text
The Climate of Venezuela is characterized for being tropical and isothermal as a result of its geographical location near the Equator, but because of the topography and the dominant wind direction, several climatic types occur which can be the same as found in temperate latitudes, and even polar regions. Latitude exerts little influence on the Venezuelan climate, but the altitude changes it dramatically, particularly the temperature, reaching values very different according to the presence of different thermal floors.
```

## 2. `ares_nq_example_2269298549089163701`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who made possible the first reproduction of the human voice on the phonograph

Answer:

> Thomas Edison

Contexts:

- Context `ares_doc_2269298549089163701`:

```text
The phonograph was invented in 1877 by Thomas Edison. While other inventors had produced devices that could record sounds, Edison's phonograph was the first to be able to reproduce the recorded sound. His phonograph originally recorded sound onto a tinfoil sheet wrapped around a rotating cylinder. A stylus responding to sound vibrations produced an up and down or hill-and-dale groove in the foil. Alexander Graham Bell's Volta Laboratory made several improvements in the 1880s and introduced the "graphophone", including the use of wax-coated cardboard cylinders and a cutting stylus that moved from side to side in a zigzag groove around the record. In the 1890s, Emile Berliner initiated the transition from phonograph cylinders to flat discs with a spiral groove running from the periphery to near the center, coining the term "gramophone" for disc record players, which is predominantly used in many languages. Later improvements through the years included modifications to the turntable and its drive system, the stylus or needle, and the sound and equalization systems.
```

## 3. `ares_nq_example_4092499579855624350`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who is rose in the fall season 2

Answer:

> September 25 , 1987

Contexts:

- Context `ares_doc_4092499579855624350`:

```text
Rose Stagg (Valene Kane), a woman who had a sexual relationship with Paul whilst at university. During a night of passion, Paul tried to strangle her to death. As the Belfast Strangler comes to the attention of the public, Stagg notices the similarities and contacts her close friend Reed Smith. Her husband was unaware the attack had taken place. She is later kidnapped and held captive by Spector. She is later found unconscious in a car trunk. During series three, Stagg reveals that her sexual relationship with Paul was entirely consensual, and that, during sex, he strangled her so aggressively she had to be revived.
```

## 4. `ares_nq_example_5147972604762913542`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when does the new season of are you the one come on

Answer:

> 1978

Contexts:

- Context `ares_doc_5147972604762913542`:

```text
Season seven premiered on August 15, 2018.
```

## 5. `ares_nq_example_9169976182548289414`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who is recognized as the founder of islam

Answer:

> on Flag Day in 1954

Contexts:

- Context `ares_doc_9169976182548289414`:

```text
The history of Islam concerns the political, social, economic and developments of Islamicate civilization. Despite concerns about the reliability of early sources, most historians believe that Islam originated in Mecca and Medina at the start of the 7th century CE, approximately 600 years after the founding of Christianity. Muslims, however, believe that it did not start with Muhammad, but that it was the original faith of others whom they regard as prophets, such as Jesus, David, Moses, Abraham, Noah and Adam.
```

## 6. `ares_nq_example_7527598871943656886`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> what languages are spoken in india the most

Answer:

> Superman

Contexts:

- Context `ares_doc_7527598871943656886`:

```text
India's central government has 23 constitutionally recognized official languages. Hindi and English are typically used as an official language by the central government. State governments use their respective official languages.
```

## 7. `ares_nq_example_6705627704423938484`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> which animal on earth has the longest life span

Answer:

> eight

Contexts:

- Context `ares_doc_6705627704423938484`:

```text
BULLET::::- Adwaita, an Aldabra giant tortoise, died at an estimated age of 255 in March 2006 in Alipore Zoo, Kolkata, India. If verified, it will have been the oldest terrestrial animal in the world.
```

## 8. `ares_nq_example_8865736331308174082`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when was the last time.michigan beat ohio state

Answer:

> Bill Russell

Contexts:

- Context `ares_doc_8865736331308174082`:

```text
Rodriguez was fired following Michigan's 2010 season, ending Michigan's flirtation with the spread—and with non-"Michigan Man" coaches. Rodriguez was succeeded by Brady Hoke, who served as Michigan's defensive line coach from 1995 to 2002. Hoke held head coaching positions at Ball State from 2003 to 2008 and San Diego State from 2009 to 2010 before returning to Michigan. Meanwhile, in Columbus, the Ohio State football program came under NCAA investigation in early 2011 for an incident in which several prominent players were discovered to have traded memorabilia for tattoos. Evidence surfaced that Tressel had known about the situation but had not reported it to school compliance officials, and that the abuses were more widespread and longstanding than originally reported. On May 30, 2011, Tressel resigned as head coach and former Buckeye player and assistant coach Luke Fickell was appointed interim head coach for the 2011 season. In July 2011, in response to the ongoing NCAA investigation, Ohio State vacated all wins from the 2010 season, including the win over Michigan, leaving Tressel with a final record against Michigan of 8–1, with a win streak of six.
```

## 9. `ares_nq_example_8707879945343660137`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> what hangs from the trees in the bayou

Answer:

> Spanish moss

Contexts:

- Context `ares_doc_8707879945343660137`:

```text
Spanish moss
```

## 10. `ares_nq_example_1917333139201003378`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who were the first non native settlers in the us

Answer:

> European colonization

Contexts:

- Context `ares_doc_1917333139201003378`:

```text
European colonization of the Americas
```

## 11. `ares_nq_example_6365160075395818746`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> points outside the production possibilities curve represent combinations of products that are

Answer:

> unattainable

Contexts:

- Context `ares_doc_6365160075395818746`:

```text
Any point that lies either on the production possibilities curve or to the left of it is said to be an attainable point: it can be produced with currently available resources. Points that lie to the right of the production possibilities curve are said to be unattainable because they cannot be produced using currently available resources. Points that lie strictly to the left of the curve are said to be inefficient, because existing resources would allow for production of more of at least one good without sacrificing the production of any other good. An efficient point is one that lies on the production possibilities curve. At any such point, more of one good can be produced only by producing less of the other.
```

## 12. `ares_nq_example_5841995020099553222`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> where does the last name cintron come from

Answer:

> Portuguese

Contexts:

- Context `ares_doc_5841995020099553222`:

```text
Cintrón or Cintron is a surname of Portuguese and Spanish-French including Sephardic origins. The name migrated as a consequence of the conquest and settlement of the New World, particularly in Puerto Rico. Famous people with the surname Cintron:
```

## 13. `ares_nq_example_839669511198247322`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> types of skiing in the winter olympics 2018

Answer:

> 775

Contexts:

- Context `ares_doc_839669511198247322`:

```text
BULLET::::- Men's downhill was postponed (high winds) from 11 to 15 February.
```

## 14. `ares_nq_example_4721622231665415813`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when was child benefit paid for the first child

Answer:

> 1975

Contexts:

- Context `ares_doc_4721622231665415813`:

```text
In 1975, the rate was increased to £1.50 for each child after the first.
```

## 15. `ares_nq_example_3559055084635054736_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> an influential religion to enter china along the silk route during the han dynasty was

Answer:

> Buddhism

Contexts:

- Context `ares_doc_3559055084635054736_2`:

```text
Chinese Buddhism
```

## 16. `ares_nq_example_1711944377965749852`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> the boiling point of water is 100 degrees celsius express this in si units

Answer:

> 100 ° C

Contexts:

- Context `ares_doc_1711944377965749852`:

```text
From 1743, the Celsius scale is based on 0 °C for the freezing point of water and 100 °C for the boiling point of water at 1 atm pressure. Prior to 1743, the scale was also based on the boiling and melting points of water, but the values were reversed (i.e. the boiling point was at 0 degrees and the melting point was at 100 degrees). The 1743 scale reversal was proposed by Jean-Pierre Christin.
```

## 17. `ares_nq_example_3568942573258999273`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> what is the ultimate objective of financial management

Answer:

> Profit maximization

Contexts:

- Context `ares_doc_3568942573258999273`:

```text
BULLET::::- Profit maximization happens when marginal cost is equal to marginal revenue. This is the main objective of Financial Management.
```

## 18. `ares_nq_example_243685073103458654`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> what was the initial effect of the transition from command to market economies in eastern europe

Answer:

> July 14 , 1976

Contexts:

- Context `ares_doc_243685073103458654`:

```text
Inequality of opportunity was higher in the transition economies of Central and Eastern Europe and Central Asia than in some other developed economies in Western Europe (except France, where inequality of opportunity was relatively high). The highest inequality of opportunity was found in the Balkans and Central Asia. In terms of legal regulations and access to education and health services, inequality of opportunity related to gender was low in Europe and Central Asia but medium to high in respect of labour practices, employment and entrepreneurship and in access to finance. In Central Asia women also experienced significant lack of access to health services, as was the case in Arab countries. While many transition economies performed well with respect to primary and secondary education, and matched that available in many other developed economies, they were weaker when it came to training and tertiary education.
```

## 19. `ares_nq_example_5745040113272333526`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> where does the saskatchewan river start and end

Answer:

> central Saskatchewan

Contexts:

- Context `ares_doc_5745040113272333526`:

```text
The North Saskatchewan River is a glacier-fed river that flows from the Canadian Rockies continental divide east to central Saskatchewan, where it joins with another major river to make up the Saskatchewan River. Its water flows eventually into the Hudson Bay.
```

## 20. `ares_nq_example_7729388021714760854`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when was the rock and roll hall of fame built in cleveland

Answer:

> Brotherly Love

Contexts:

- Context `ares_doc_7729388021714760854`:

```text
The museum was dedicated on September 1, 1995, with the ribbon being cut by an ensemble that included Yoko Ono and Little Richard, among others, before a crowd of more than 10,000 people. The following night an all-star concert was held at Cleveland Stadium. It featured Chuck Berry, Bob Dylan, Al Green, Jerry Lee Lewis, Aretha Franklin, Bruce Springsteen, Iggy Pop, John Fogerty, John Mellencamp, and many others.
```

## 21. `ares_nq_example_426246770431284105_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> type of disappearing lake found in limestone areas in the west of ireland

Answer:

> Tami Lynn

Contexts:

- Context `ares_doc_426246770431284105_2`:

```text
A turlough, or turlach, is a type of disappearing lake found mostly in limestone areas of Ireland, west of the River Shannon. The name comes from the Irish "tur", meaning "dry", with the suffix "-lach", meaning "a place" (in an abstract sense). The "-lach" suffix is often mistakenly spelled and/or thought to refer to the word "loch", the Irish, Scottish Gaelic and Scots word for "lake". The landforms are found in Irish karst (exposed limestone) areas.
```

## 22. `ares_nq_example_1870248091120409120`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> where did the potter's wheel first develop

Answer:

> runoff

Contexts:

- Context `ares_doc_1870248091120409120`:

```text
The earliest forms of the potter's wheel (called "tourneys" or "slow wheels") were probably developed as an extension to this procedure. Tournettes, in use around 4500 BC in the Near East, were turned slowly by hand or by foot while coiling a pot. Only a small range of vessels were fashioned on the tournette, suggesting that it was used by a limited number of potters. The introduction of the slow wheel increased the efficiency of hand-powered pottery production.
```

## 23. `ares_nq_example_7607921794902030568`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> why did jean valjean take care of cosette

Answer:

> the ARPANET project

Contexts:

- Context `ares_doc_7607921794902030568`:

```text
A short chapter, mainly consisting of two newspaper articles, informs the reader, that Jean Valjean has been re-arrested while getting into the stagecoach to Montfermeil (on his way to get Fantine's eight-year-old daughter, Cosette, whom he had promised to rescue). In July 1823, he was condemned to death for the 40-sous theft and the escape from the jail in Montreuil-sur-Mer, as the prosecutor claims that Valjean was part of a gang of street robbers and the latter refuses to defend himself. His sentence was graciously reduced by the king to only life in prison instead of death. Before he was captured, Jean Valjean had already traveled near to Montfermeil and buried all the money he'd saved as M. Madeleine—a chapter tells of a worker in Montfermeil, a former Toulon convict, who claims having seen, according to a local fairy tale, the devil burying his treasure in the forest. No further explanation is ever given as to why, having buried his money near Montfermeil, Valjean had traveled back to Paris and then attempted to travel back to Montfermeil.
```

## 24. `ares_nq_example_1986464037797500492`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when did the jurassic park movies come out

Answer:

> Dan Stevens

Contexts:

- Context `ares_doc_1986464037797500492`:

```text
The book was successful, as was Steven Spielberg's 1993 film adaptation. The film received a theatrical 3D re-release in 2013, and was selected in 2018 for preservation in the United States National Film Registry by the Library of Congress as being "culturally, historically, or aesthetically significant." A sequel novel, "The Lost World", was published in 1995, followed by in 1997.
```

## 25. `ares_nq_example_5608421991404219229_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> where does the last name hansen come from

Answer:

> 228 minutes

Contexts:

- Context `ares_doc_5608421991404219229_2`:

```text
Hansen or Hanssen () is a Scandinavian patronymic surname, meaning "son of Hans". As of 2008, it is the third most common surname in Denmark, shared by 4.3% of the population. As of 2000, "Hansen" is the single most common surname in Norway, not counting spelling variations such as "Hanssen", which are also quite common. In the Faroe Islands "Hansen" is the second most common surname, while in the North German federal states of Schleswig-Holstein and Hamburg "Hansen" is the third and fifth most common surname, respectively.
```

## 26. `ares_nq_example_6553353802049563745`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when did the twenty one pilots hiatus start

Answer:

> 1992

Contexts:

- Context `ares_doc_6553353802049563745`:

```text
In an interview with "Alternative Press" in November 2016, Twenty One Pilots stated that after their last show, they will be "going dark" to focus on new music. Joseph stated that he would like to focus on lyrical content of the music, and bring the music back to the "authenticity, lyrics, delivery, and fearlessness of songwriting" similar to that of the self-titled album. The band's last activity came in July 2017 in the form of posts on social media depicting an eye closing over lyrics from several of their songs.
```

## 27. `ares_nq_example_923934477516364422`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who enforces the charter of rights and freedoms

Answer:

> Charlotte of Mecklenburg - Strelitz

Contexts:

- Context `ares_doc_923934477516364422`:

```text
One of the most notable effects of the adoption of the Charter was to greatly expand the scope of judicial review, because the Charter is more explicit with respect to the guarantee of rights and the role of judges in enforcing them than was the Bill of Rights. The courts, when confronted with violations of Charter rights, have struck down unconstitutional federal and provincial statutes and regulations or parts of statutes and regulations, as they did when Canadian case law was primarily concerned with resolving issues of federalism. The Charter, however, granted new powers to the courts to enforce remedies that are more creative and to exclude more evidence in trials. These powers are greater than what was typical under the common law and under a system of government that, influenced by Canada's parent country the United Kingdom, was based upon Parliamentary supremacy. As a result, the Charter has attracted both broad support from a majority of the Canadian electorate and criticisms by opponents of increased judicial power. The Charter only applies to government laws and actions (including the laws and actions of federal, provincial, and municipal governments and public school boards), and sometimes to the common law, not to private activity.
```

## 28. `ares_nq_example_8229835206359765152`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when did it become law to stand for the national anthem

Answer:

> June 22 , 1942

Contexts:

- Context `ares_doc_8229835206359765152`:

```text
When the U.S. national anthem was first recognized by law in 1931, there was no prescription as to behavior during its playing. On June 22, 1942, the law was revised indicating that those in uniform should salute during its playing, while others should simply stand at attention, men removing their hats. The same code also required that women should place their hands over their hearts when the flag is displayed during the playing of the national anthem, but not if the flag was not present. On December 23, 1942, the law was again revised instructing men and women to stand at attention and face in the direction of the music when it was played. That revision also directed men and women to place their hands over their hearts only if the flag was displayed. Those in uniform were required to salute. On July 7, 1976, the law was simplified. Men and women were instructed to stand with their hands over their hearts, men removing their hats, irrespective of whether or not the flag was displayed and those in uniform saluting. On August 12, 1998, the law was rewritten keeping the same instructions, but differentiating between "those in uniform" and "members of the Armed Forces and veterans" who were both instructed to salute during the playing whether or not the flag was displayed. Because of the changes in law over the years and confusion between instructions for the Pledge of Allegiance versus the National Anthem, throughout most of the 20th century many people simply stood at attention or with their hands folded in front of them during the playing of the Anthem, and when reciting the Pledge they would hold their hand (or hat) over their heart. After 9/11, the custom of placing the hand over the heart during the playing of the national anthem became nearly universal.
```

## 29. `ares_nq_example_2053640931063416368`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> known as the punk poet who used poetry in their music

Answer:

> New York Yankees

Contexts:

- Context `ares_doc_2053640931063416368`:

```text
John Cooper Clarke
```

## 30. `ares_nq_example_7368254478874801356`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who is the head of the department of homeland security 2017

Answer:

> in the Gospel of Luke

Contexts:

- Context `ares_doc_7368254478874801356`:

```text
Kevin McAleenan is the Acting Secretary of Homeland Security, upon the resignation of Kirstjen Nielsen.
```

## 31. `ares_nq_example_9084604251611519852`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> why does cooling water run through the condenser

Answer:

> November 13 , 1997

Contexts:

- Context `ares_doc_9084604251611519852`:

```text
Cooling towers originated in the 19th century through the development of condensers for use with the steam engine. Condensers use relatively cool water, via various means, to condense the steam coming out of the cylinders or turbines. This reduces the back pressure, which in turn reduces the steam consumption, and thus the fuel consumption, while at the same time increasing power and recycling boiler-water. However the condensers require an ample supply of cooling water, without which they are impractical. The consumption of cooling water by inland processing and power plants is estimated to reduce power availability for the majority of thermal power plants by 2040–2069. While water usage is not an issue with marine engines, it forms a significant limitation for many land-based systems.
```

## 32. `ares_nq_example_2845443756485516190`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> where does the eurostar train arrives in london

Answer:

> the New England Patriots

Contexts:

- Context `ares_doc_2845443756485516190`:

```text
The London terminus is St Pancras International, the other British calling points being Ebbsfleet International and Ashford International in Kent. Intermediate calling points in France are Calais-Fréthun and Lille-Europe, with trains to Paris terminating at Gare du Nord. Trains to Belgium terminate at Midi/Zuid station in Brussels. The only intermediate calling station in the Netherlands is Rotterdam Centraal, with trains terminating at Amsterdam Centraal. In addition, there are direct services from London to Disneyland Paris at Marne-la-Vallée – Chessy, direct services to southern France (Lyon, Avignon and Marseille), and seasonal direct services to the French Alps in winter (December to April).
```

## 33. `ares_nq_example_3492797766982308854`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when do mr schuester and emma get together

Answer:

> the fourth season

Contexts:

- Context `ares_doc_3492797766982308854`:

```text
Emma Pillsbury Schuester (previously Pillsbury-Howell) is a fictional character from the Fox musical comedy-drama series "Glee". Portrayed by actress Jayma Mays, Emma has appeared in "Glee" from its pilot episode, first broadcast on May 19, 2009. Emma was developed by "Glee" creators Ryan Murphy, Brad Falchuk and Ian Brennan. She is a guidance counselor at the fictional William McKinley High School in Lima, Ohio where the series is set. Emma suffers from obsessive-compulsive disorder and has romantic feelings for glee club director Will Schuester (Matthew Morrison), but becomes engaged to football coach Ken Tanaka (Patrick Gallagher) as Will is married. Ken ultimately breaks up with her on their wedding day because of her feelings for Will, and when Will leaves his wife Terri (Jessalyn Gilsig), he and Emma share a kiss. Their relationship is short-lived, and in the second season, Emma and her dentist boyfriend Carl Howell (John Stamos) marry in Las Vegas. The wedding is later annulled as it was unconsummated. At the beginning of the third season, she and Will are living together; they become engaged shortly after New Years, and consummate their relationship near the end of the school year. Emma leaves Will at the altar midway through the fourth season, but the two later reconcile and marry in the season finale. She becomes pregnant during the middle of the fifth season.
```

## 34. `ares_nq_example_684058159028311642_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when did are you smarter than a 5th grader first air

Answer:

> February 27 , 2007

Contexts:

- Context `ares_doc_684058159028311642_2`:

```text
Are You Smarter than a 5th Grader? is an American quiz game show that airs on Nickelodeon and is hosted by John Cena. It previously aired on Fox where it was hosted by Jeff Foxworthy. It is produced by Mark Burnett. The show premiered as a three-day special which began on February 27, 2007 with the first two shows each a half-hour in length. Regular one-hour episodes began airing Thursdays from March 1 through May 10, and the first season continued with new episodes beginning May 31. "Are You Smarter Than a 5th Grader?" was picked up for the 2007–08 season, which began on September 6, 2007, and aired in the same timeslot. Following the end of the original run of the primetime version on September 18, 2009, a first-run syndicated version of the show ran from September 2009 to May 2011, with Foxworthy returning as host. On May 26, 2015, the program returned to Fox for a new, 4th season, with Foxworthy, again, returning as host. On February 14, 2019, it was announced that the program would be revived on Nickelodeon with new host John Cena, with the revival premiering on June 10, 2019.
```

## 35. `ares_nq_example_6268752976507719216`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when do you celebrate birthday if born on feb 29

Answer:

> February 28

Contexts:

- Context `ares_doc_6268752976507719216`:

```text
A person born on February 29 may be called a "leapling", a "leaper", or a "leap-year baby". In non-leap years, some leaplings celebrate their birthday on either February 28 or March 1, while others only observe birthdays on the authentic intercalary date, February 29.
```

## 36. `ares_nq_example_765448266799898575`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when did the newest macbook pro come out

Answer:

> June 5 , 2017

Contexts:

- Context `ares_doc_765448266799898575`:

```text
On June 5, 2017, Apple updated the line with Intel Kaby Lake processors and newer graphics cards. Additionally, the 13-inch model now comes with a 128GB storage option, down from the base 256GB storage. New symbols are introduced to the control and option keys. On July 12, 2018, Apple updated the Touch Bar models with Intel Coffee Lake quad-core processors in 13-inch models and six-core processors in 15-inch models, updated graphics cards, improved third-generation butterfly keyboards, Bluetooth 5, T2 SoC Chip, True Tone display technology, and larger capacity batteries. The 15-inch model can also be configured with up to 4TB of storage, 32GB of DDR4 memory and a Core i9 processor. In late November the higher-end 15-inch model could be configured with Radeon Pro Vega graphics. On May 21, 2019 Apple announced updated Touch Bar models with newer processors, with an eight-core Core i9 standard for the higher-end 15-inch model, and an updated keyboard manufactured with "new materials" across the line. On July 9, 2019 Apple updated the 13-inch model with two Thunderbolt ports with newer processors and graphics, True Tone display technology, and replaced the function keys with the Touch Bar. macOS Catalina will add support for Dolby Atmos, Dolby Vision, and HDR10 on 2018 and newer models.
```

## 37. `ares_nq_example_8466196474705624263`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who was running as vice president in 1984

Answer:

> Ferraro

Contexts:

- Context `ares_doc_8466196474705624263`:

```text
Geraldine Ferraro
```

## 38. `ares_nq_example_2522076069840987893`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who played cory's older brother on boy meets world

Answer:

> four

Contexts:

- Context `ares_doc_2522076069840987893`:

```text
Eric Randall Matthews (Will Friedle) is the elder brother of Cory, Morgan, and Joshua Matthews. He began the show as a suave, popular young man, who constantly went out on dates. He was originally portrayed as the stereotypical elder brother. Eric's character changed mid-series from preppy elder brother to "crazy, moronic brother". During the fourth season, Eric takes a year off from school when he doesn't get into a college of his choice.
```

## 39. `ares_nq_example_6662395259728504920`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who directed the iconic animated short educational film ek anek aur ekta

Answer:

> Vijaya Mulay

Contexts:

- Context `ares_doc_6662395259728504920`:

```text
The film was directed by Vijaya Mulay. The film's design, animation and creation was done by Bhimsain Khurana. The lyrics of "Hind Desh ke Niwasi" were written by Pandit Vinay Chandra Maudgalya. Sadhna Sargam sang "Ek Chidiya, Anek Chidiyan". The assistants were S.M. Hasan, Mahesh Taavre and Girish Rao. The film won the National Film Award for Best Educational Film., and it was the first film from the animation studios of then Center for Education Technology. The film also won the Best Children's Film award in Japan. The film is considered to be one of India's greatest examples of animation story-telling, and well remembered by the 80s generation as a classic illustration of "Anekta mein Ekta".
```

## 40. `ares_nq_example_6751220433242447969_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> how many seasons of the bastard executioner are there

Answer:

> one

Contexts:

- Context `ares_doc_6751220433242447969_2`:

```text
The Bastard Executioner
```

## 41. `ares_nq_example_4046851836203380467`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> legislation regarding data protection and security in uk

Answer:

> Leo Arnaud

Contexts:

- Context `ares_doc_4046851836203380467`:

```text
The Data Protection Act 1998 (c 29) was a United Kingdom Act of Parliament designed to protect personal data stored on computers or in an organised paper filing system. It enacted the EU Data Protection Directive 1995's provisions on the protection, processing and movement of data.
```

## 42. `ares_nq_example_6544639991517260033_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> what parts make up the peripheral nervous system

Answer:

> the Pandavas

Contexts:

- Context `ares_doc_6544639991517260033_2`:

```text
The peripheral nervous system is divided into the somatic nervous system and the autonomic nervous system. In the somatic nervous system, the cranial nerves are part of the PNS with the exception of the optic nerve (cranial nerve II), along with the retina. The second cranial nerve is not a true peripheral nerve but a tract of the diencephalon. Cranial nerve ganglia originated in the CNS. However, the remaining ten cranial nerve axons extend beyond the brain and are therefore considered part of the PNS. The autonomic nervous system exerts involuntary control over smooth muscle and glands. The connection between CNS and organs allows the system to be in two different functional states: sympathetic and parasympathetic.
```

## 43. `ares_nq_example_7032694139181071944`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> what information is displayed in clear text from the ftp header

Answer:

> Paradise , Nevada

Contexts:

- Context `ares_doc_7032694139181071944`:

```text
FTP does not encrypt its traffic; all transmissions are in clear text, and usernames, passwords, commands and data can be read by anyone able to perform packet capture (sniffing) on the network. This problem is common to many of the Internet Protocol specifications (such as SMTP, Telnet, POP and IMAP) that were designed prior to the creation of encryption mechanisms such as TLS or SSL.
```

## 44. `ares_nq_example_7639529212077881462_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> where was the movie silver linings playbook filmed

Answer:

> October 2012

Contexts:

- Context `ares_doc_7639529212077881462_2`:

```text
After eight months of treatment in a mental health facility for bipolar disorder, Patrizio "Pat" Solitano, Jr. (Bradley Cooper) is released into the care of his father Patrizio, Sr. (Robert De Niro) and mother Dolores (Jacki Weaver) at his childhood home in Upper Darby, Pennsylvania. His main focus is to reconcile with his ex-wife, Nikki (Brea Bee). She has moved away and obtained a restraining order against him after Pat had found her in the shower with another man and badly beat him. During his time in the clinic Pat befriends Danny McDaniels (Chris Tucker), an easygoing man who is embroiled in a legal dispute with the clinic on whether or not he is eligible to leave. Pat's therapist, Dr. Patel (Anupam Kher), does his best to convince him to keep taking his medication, as a repeat of his violent outbursts might send him back to the clinic. But Pat tells him that he has a new outlook on life: he attempts to see the good, or silver linings, in all that he experiences. Patrizio employs the Latin phrase "Excelsior" translated as "always higher" or "ever upward" as the mantra of his new positive outlook.
```

## 45. `ares_nq_example_1996292107460275608`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> where was the movie a walk among the tombstones filmed

Answer:

> New York City

Contexts:

- Context `ares_doc_1996292107460275608`:

```text
Filming began on March 3, 2013 in New York City. Producers invited author Block to the set to watch filming. On the casting of Neeson, Block said, "Readers often ask who'd be my ideal Matt Scudder, and I usually change the subject. But now it's safe to tell you that, ever since I saw him in "Michael Collins", Neeson has been up at the top of my personal Scudder wish list. I couldn't be happier about either the star or the writer/director, both of them genuine artists and brilliant professionals. My book's in good hands."
```

## 46. `ares_nq_example_9187994979510737197`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who's the model on let's make a deal

Answer:

> September 27 , 2017

Contexts:

- Context `ares_doc_9187994979510737197`:

```text
Tiffany Adams Coyne (born May 6, 1982) is an American model and dancer. She is the model on "Let's Make a Deal", having replaced Alison Fiori in 2009.
```

## 47. `ares_nq_example_5320268832129970522`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> what is the number of basic units in the international system of units

Answer:

> seven

Contexts:

- Context `ares_doc_5320268832129970522`:

```text
The SI base units are seven units of measure defined by the International System of Units as the basic set from which all other SI units can be derived. The units and their physical quantities are the second for time, the metre for measurement of length, the kilogram for mass, the ampere for electric current, the kelvin for temperature, the mole for amount of substance, and the candela for luminous intensity.
```

## 48. `ares_nq_example_6145868466021183224`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who played solomon in little house on the prairie

Answer:

> Todd Bridges

Contexts:

- Context `ares_doc_6145868466021183224`:

```text
BULLET::::- Solomon Henry (played by Todd Bridges)
```

## 49. `ares_nq_example_3612945562446452821`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when were 7 books removed from the bible

Answer:

> 1546

Contexts:

- Context `ares_doc_3612945562446452821`:

```text
Finally the Council of Trent (1546 AD) adopted an understanding of the canons of these previous councils as corresponding to its own list of deuterocanonical books. This understanding rested on two historical presumptions which are contested in current research; that where these councils and synods noted the 'Book of Jeremiah', they intended the Book of Baruch to be silently understood (including the Letter of Jeremiah); and that where these synods and councils noted 'two books of Esdras', these two books were to be understood as Ezra and Nehemiah counted separately, not (as was universal in Septuagint manuscripts of the time, in the Old Latin Bible and in the works of Augustine) as 1 Esdras and Ezra–Nehemiah.
```

## 50. `ares_nq_example_4094570070863238215`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when does the second part of vikings season 4 start

Answer:

> Lou Rawls

Contexts:

- Context `ares_doc_4094570070863238215`:

```text
The fourth season consists of a double order of twenty episodes, split into two parts of ten episodes; the second half premiered on November 30, 2016. The season follows the battles between Ragnar and Rollo in Francia, Bjorn's raid into the Mediterranean, and the Viking invasion of England. It concluded in its entirety on February 1, 2017.
```

## 51. `ares_nq_example_7602825500085978355`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who sang for lee bowman in my dream is yours

Answer:

> Hal Derwin

Contexts:

- Context `ares_doc_7602825500085978355`:

```text
BULLET::::- Lee Bowman as Gary Mitchell (singing voice was dubbed by Hal Derwin)
```

## 52. `ares_nq_example_3908725222525421557`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> what role does the president play in foreign affairs

Answer:

> negotiates treaties with foreign nations

Contexts:

- Context `ares_doc_3908725222525421557`:

```text
Subject to the advice and consent role of the U.S. Senate, the President of the United States negotiates treaties with foreign nations, but treaties enter into force only if ratified by two-thirds of the Senate. The President is also Commander in Chief of the United States Armed Forces, and as such has broad authority over the armed forces. Both the Secretary of State and ambassadors are appointed by the President, with the advice and consent of the Senate. The United States Secretary of State acts similarly to a foreign minister and under Executive leadership is the primary conductor of state-to-state diplomacy.
```

## 53. `ares_nq_example_4373262132142058334`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> mention the chemical change that proinsulin undergo to be able to act as mature insulin

Answer:

> government department

Contexts:

- Context `ares_doc_4373262132142058334`:

```text
The post translational modification of proinsulin to mature insulin only occurs in the beta cells of the islets of Langerhans. When proinsulin is transported through the Golgi apparatus the C-peptide is cleaved. This cleavage occurs with the aid of two endoproteases. Type I endoproteases, PC1 and PC3, disrupt the C peptide-B chain connection. PC2, a type II endoprotease, cleaves the C peptide-A chain bond. The resulting molecule, now mature insulin, is stored as a hexamer in secretory vesicles and is stabilized with formula_1 molecules until it is secreted.
```

## 54. `ares_nq_example_4199405438415986663_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when does the second half of vikings season 5 air

Answer:

> Ozzie Smith

Contexts:

- Context `ares_doc_4199405438415986663_2`:

```text
The fifth season consists of a double order of twenty episodes, split into two parts of ten episodes; the second half premiered on November 28, 2018, The premise of the fifth season differs from the previous four after the departure of Travis Fimmel as Ragnar, and it now follows the adventures of his sons. Jonathan Rhys Meyers is introduced as a major character, after his initial appearance in the fourth season's finale. The season concluded in its entirety on January 30, 2019.
```

## 55. `ares_nq_example_7805719588487348587`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when did the vikings first sail and reach britain

Answer:

> 6 January 793

Contexts:

- Context `ares_doc_7805719588487348587`:

```text
During the reign of King Beorhtric of Wessex (786–802) three ships of "Northmen" landed at Portland Bay in Dorset. The local reeve mistook the Vikings for merchants and directed them to the nearby royal estate, but the visitors killed him and his men. The earliest recorded planned Viking raid, on 6 January 793, targeted the monastery on the island of Lindisfarne, off the north-east coast of Northumbria. According to the 12th-century Anglo-Norman chronicler Symeon of Durham, the raiders killed the resident monks or threw them into the sea to drown or carried them away as slaves—along with some of the church treasures. In 875, after enduring eight decades of repeated Viking raids, the monks fled Lindisfarne, carrying the relics of Saint Cuthbert with them.
```

## 56. `ares_nq_example_3867705141367202061`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who sings ive loved you for a thousand years

Answer:

> Christina Perri

Contexts:

- Context `ares_doc_3867705141367202061`:

```text
A Thousand Years (Christina Perri song)
```

## 57. `ares_nq_example_119543419987074002`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who played anne in anne with an e

Answer:

> Amybeth McNulty

Contexts:

- Context `ares_doc_119543419987074002`:

```text
Approximately 1800 girls on three continents auditioned for the role of Anne Shirley. Amybeth McNulty was chosen for her ability to deliver dialogue which is "incredibly thick and dynamic and beautiful", according to Miranda de Pencier. Walley-Beckett describes her as at once "luminous", transparent, smart, soulful and emotional. According to an interview with McNulty, an Irish Canadian whose career on stage has included roles in "Annie", "The Sound of Music", and "Oliver!", and on screen in "Agatha Raisin" and "Clean Break", her audition for "Anne" "consisted of talking to trees, chatting with flowers and building thrones out of twigs."
```

## 58. `ares_nq_example_2870089333524299909_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who has won the 2018 formula one australia grand prix tournament

Answer:

> mid-March

Contexts:

- Context `ares_doc_2870089333524299909_2`:

```text
Ferrari driver Sebastian Vettel was the defending race winner. Lewis Hamilton started the race from pole—his seventh pole position in Australia, a record for the event—while Vettel successfully defended his race win, the forty-eighth of his career.
```

## 59. `ares_nq_example_6785327703850595221_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who has climbed mount everest the number of times

Answer:

> Bill Russell

Contexts:

- Context `ares_doc_6785327703850595221_2`:

```text
BULLET::::- On 11 May 2011, Apa Sherpa successfully reached the summit of Everest for the twenty-first time, breaking his own record for the most successful ascents. He first climbed Mount Everest in 1989 at the age of 29.
```

## 60. `ares_nq_example_6449103613087792543`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> where do the sharks play in san jose

Answer:

> SAP Center at San Jose

Contexts:

- Context `ares_doc_6449103613087792543`:

```text
The San Jose Sharks are a professional ice hockey team based in San Jose, California. They are members of the Pacific Division of the Western Conference of the National Hockey League (NHL). The franchise is owned by San Jose Sports & Entertainment Enterprises. Beginning play in the 1991–92 season, the Sharks initially played their home games at the Cow Palace, before they moved to their present home, now named SAP Center at San Jose, in 1993. The SAP Center is known locally as the Shark Tank.
```

## 61. `ares_nq_example_6648524536408285205`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> what is the first book of percy jackson

Answer:

> The Lightning Thief

Contexts:

- Context `ares_doc_6648524536408285205`:

```text
Development for both "The Lightning Thief" and the "Percy Jackson" series commenced when Rick Riordan began making stories for his son Haley Riordan, who had at the time been diagnosed with ADHD and dyslexia. His son, Haley, had been studying Greek mythology in second grade and requested that his father tell him bedtime stories based on Greek myths. When Rick Riordan ran out of myths, his son suggested that he make up new stories using existing mythological characters and new ones. This led Riordan to create the fictional character of Percy Jackson and create the story of how he travels across the United States to recover Zeus' lightning-bolt. Haley suggested that he should turn that story into a book, and Riordan wrote the book over the next year despite being busy at that time.
```

## 62. `ares_nq_example_6047989319894692111`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who has a ring of power in lotr

Answer:

> Nancy Jean Cartwright

Contexts:

- Context `ares_doc_6047989319894692111`:

```text
Sauron
```

## 63. `ares_nq_example_5147972604762913542_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when does the new season of are you the one come on

Answer:

> 2018

Contexts:

- Context `ares_doc_5147972604762913542_2`:

```text
Season seven premiered on August 15, 2018.
```

## 64. `ares_nq_example_3330795627417233017`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> what was the ancient chinese umbrella used for

Answer:

> a defense against rain

Contexts:

- Context `ares_doc_3330795627417233017`:

```text
The Chinese character for umbrella is 傘 ("sǎn") and is a pictograph resembling the modern umbrella in design. Some investigators have supposed that its invention was first created by tying large leaves to bough-like ribs (the branching out parts of an umbrella). Others assert that the idea was probably derived from the tent, which remains in an unaltered form to the present day. However, the tradition existing in China is that it originated in standards and banners waving in the air, hence the use of the umbrella was often linked to high-ranking (though not necessarily royalty) in China. On at least one occasion, twenty-four umbrellas were carried before the Emperor when he went out hunting. The umbrella served in this case as a defense against rain rather than sun. The Chinese design was later brought to Japan via Korea and also introduced to Persia and the Western world via the Silk Road. The Chinese and Japanese traditional parasol, often used near temples, remains similar to the original ancient Chinese design.
```

## 65. `ares_nq_example_8488975200279464488`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when was the last time minnesota vikings was in the super bowl

Answer:

> XI

Contexts:

- Context `ares_doc_8488975200279464488`:

```text
Since the team's first season in 1961, the Vikings have had one of the highest winning percentages in the NFL. As of 2017, they have won at least three games in every season except in 1962, and are one of only six NFL teams to win at least 15 games in a regular season. The Vikings have won one NFL Championship, in 1969, before the league's merger with the American Football League (AFL). Since the league merger in 1970, they have qualified for the playoffs 27 times, third-most in the league. The team has played in Super Bowls IV, VIII, IX, and XI, though failing to win any of them. In addition, they have lost in their last six NFC Championship Game appearances since 1978. The team currently has 14 members in the Pro Football Hall of Fame.
```

## 66. `ares_nq_example_6291722830448463311_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who does luke skywalker fall in love with

Answer:

> Mara Jade

Contexts:

- Context `ares_doc_6291722830448463311_2`:

```text
The character also briefly appears in the "Star Wars" prequel "" as an infant. The Expanded Universe depicts him as a powerful Jedi Master, the husband of Mara Jade, father of Ben Skywalker and maternal uncle of Jaina, Jacen and Anakin Solo.
```

## 67. `ares_nq_example_5156262494346608389`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> how many episodes in game if thrones season 7

Answer:

> Anglican church

Contexts:

- Context `ares_doc_5156262494346608389`:

```text
The seventh and penultimate season of the fantasy drama television series "Game of Thrones" premiered on HBO on July 16, 2017, and concluded on August 27, 2017. Unlike previous seasons, which consisted of ten episodes each, the seventh season consisted of only seven episodes. Like the previous season, it largely consisted of original content not found in George R. R. Martin's "A Song of Ice and Fire" series, while also incorporating material that Martin revealed to showrunners about the upcoming novels in the series. The series was adapted for television by David Benioff and D. B. Weiss.
```

## 68. `ares_nq_example_5874093358022821909`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> what proposition made the insurance commissioner an elected position

Answer:

> Proposition 103

Contexts:

- Context `ares_doc_5874093358022821909`:

```text
As a result of the passage of Proposition 103 in 1988, the elected office of the California Insurance Commissioner was created in 1991. Previously, the position was held by a person appointed by the Governor. The Insurance Commissioner oversees the Department of Insurance. Democrat Dave Jones won the November 2, 2010 election for California Insurance Commissioner.
```

## 69. `ares_nq_example_3411217364166344563_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when was harry potter and the philosophers stone published

Answer:

> by week 4 of development

Contexts:

- Context `ares_doc_3411217364166344563_2`:

```text
The book was first published in the United Kingdom on 26 June 1997 by Bloomsbury. It was published in the United States the following year by Scholastic Corporation under the title Harry Potter and the Sorcerer's Stone. It won most of the British book awards that were judged by children and other awards in the US. The book reached the top of the "New York Times" list of best-selling fiction in August 1999 and stayed near the top of that list for much of 1999 and 2000. It has been translated into at least 73 other languages, and has been made into a feature-length film of the same name, as have all six of its sequels.
```

## 70. `ares_nq_example_2717754120713429146`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who sings i feel love with the blue man group

Answer:

> Annette Strean

Contexts:

- Context `ares_doc_2717754120713429146`:

```text
Venus Hum is an electronic pop music group from Nashville, Tennessee, consisting of vocalist Annette Strean and multi-instrumentalists Kip Kubin and Tony Miracle. Miracle has a rare heart condition which results in perpetually hearing his own heartbeat in his ears. This condition is known as "venous hum", from which the group's name is derived.
```

## 71. `ares_nq_example_1106714590515566575`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who was the head of the spanish inquisition

Answer:

> drilling exploratory wells

Contexts:

- Context `ares_doc_1106714590515566575`:

```text
The most famous Inquisitor General was the Spanish Dominican Tomás de Torquemada, who spearheaded the Spanish Inquisition.
```

## 72. `ares_nq_example_6848877582744849076_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> first dynasty to issue gold coins in india

Answer:

> 2018

Contexts:

- Context `ares_doc_6848877582744849076_2`:

```text
The Gupta Empire produced large numbers of gold coins depicting the Gupta kings performing various rituals, as well as silver coins clearly influenced by those of the earlier Western Satraps by Chandragupta II.
```

## 73. `ares_nq_example_679914466501587278`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who is under the mask of darth vader

Answer:

> Cliff Richard

Contexts:

- Context `ares_doc_679914466501587278`:

```text
Shaw was particularly known for his performances in productions of Shakespeare plays which were considered daring and ahead of their time. In 1966, he joined the Royal Shakespeare Company, where he remained for a decade and delivered some of his most acclaimed performances. He also wrote several poems and a novel, "The Christening", in 1975. He is also known for his brief but important performance in "Return of the Jedi", the original third installment in the "Star Wars" franchise, in which he portrayed an unmasked and redeemed Anakin Skywalker (formerly Darth Vader), and his ghost in the original version of the film.
```

## 74. `ares_nq_example_8616078013378632610`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who said that religion is the opiate of the masses

Answer:

> Karl Marx .

Contexts:

- Context `ares_doc_8616078013378632610`:

```text
"Religion is the opium of the people" is one of the most frequently paraphrased statements of German philosopher and economist Karl Marx. It was translated from the German original, and is often rendered as "religion... is the opiate of the "masses"."
```

## 75. `ares_nq_example_1411792450237623098_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> which of the following helmiths feeds on blood

Answer:

> Necator americanus

Contexts:

- Context `ares_doc_1411792450237623098_2`:

```text
Helminths may cause iron-deficiency anemia. This is most severe in heavy hookworm infections, as "Necator americanus" and "Ancylostoma duodenale" feed directly on the blood of their hosts. Although the daily consumption of an individual worm (0.02–0.07 ml and 0.14–0.26 ml respectively) is small, the collective consumption under heavy infection can be clinically significantly. Intestinal whipworm may also cause anemia. Anemia has also been associated with reduced stamina for physical labor, a decline in the ability to learn new information, and apathy, irritability, and fatigue. A study of the effect of deworming and iron supplementation in 47 students from the Democratic Republic of the Congo found that the intervention improved cognitive function. Another study found that in 159 Jamaican schoolchildren, deworming led to better auditory short-term memory and scanning and retrieval of long-term memory over a period of nine-weeks.
```

## 76. `ares_nq_example_1130612447890033483`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who played sarah hedley in when the boat comes in

Answer:

> Rosalind Bailey

Contexts:

- Context `ares_doc_1130612447890033483`:

```text
BULLET::::- Rosalind Bailey as Sarah Headley née Lytton (1977, 81 / Series 2-4 / 23 episodes)
```

## 77. `ares_nq_example_590834235052106634`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> what is the name for the ch3coo- ion

Answer:

> polyatomic anion

Contexts:

- Context `ares_doc_590834235052106634`:

```text
An acetate is a salt formed by the combination of acetic acid with an alkaline, earthy, metallic or nonmetallic and other base. "Acetate" also describes the conjugate base or ion (specifically, the negatively charged ion called an anion) typically found in aqueous solution and written with the chemical formula . The neutral molecules formed by the combination of the acetate ion and a "positive" ion (called a cation) are also commonly called "acetates" (hence, "acetate of lead", "acetate of aluminum", etc.). The simplest of these is hydrogen acetate (called acetic acid) with corresponding salts, esters, and the polyatomic anion , or .
```

## 78. `ares_nq_example_2136443645297570089`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when was i can only imagine the song released

Answer:

> 2001

Contexts:

- Context `ares_doc_2136443645297570089`:

```text
"I Can Only Imagine" is a song by Christian rock band MercyMe. Written and composed by lead singer Bart Millard, the song was originally written for the band's 1999 independent album "The Worship Project" before being included on their 2001 major-label debut album "Almost There". The song was the last to be written for "The Worship Project"; in writing it, Millard drew upon his thoughts about his father's death. Lyrically, it imagines what it would be like to be before God in heaven; it opens with just a piano before building to include guitar and drums.
```

## 79. `ares_nq_example_5819386267283467034`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> what year did the us hockey team won the olympics

Answer:

> Michael Crawford

Contexts:

- Context `ares_doc_5819386267283467034`:

```text
The U.S. won gold medals at the 1960 and the 1980 Olympics and more recently, silver medals at the 2002 and 2010 Olympics. The U.S. also won the 1996 World Cup of Hockey, defeating Canada in the finals. The team's most recent medal at the World Championships came with a bronze in 2018. They won the tournament in 1933 and 1960. Unlike other nations, the U.S. doesn't typically use its best NHL players in the World Championships. Instead, it provides the younger players with an opportunity to gain international experience. Overall, the team has collected eleven Olympic medals (two of them gold), nineteen World Championship medals (two of them gold), and it reached the semi-final round of the Canada Cup/World Cup five times, twice advancing to the finals and winning gold once. The U.S. has unsuccessfully never reached the World Championship final round, having lost in the semi-final round nine times since the IIHF introduced a playoff system in 1992.
```

## 80. `ares_nq_example_8521826207096650014`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who sings in walk hard the dewey cox story

Answer:

> John C. Reilly

Contexts:

- Context `ares_doc_8521826207096650014`:

```text
Walk Hard: The Dewey Cox Story is a 2007 American comedy film directed by Jake Kasdan, and written by Kasdan and co-producer Judd Apatow. It stars John C. Reilly, Jenna Fischer, Tim Meadows and Kristen Wiig. The plot echoes the storyline of 2005's Johnny Cash biopic "Walk the Line" and 2004's Ray Charles biopic "Ray". "Walk Hard" is a parody of the biopic genre as a whole.
```

## 81. `ares_nq_example_8227939188793834871_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> what features of muscle contraction can be determined from an emg (electromyogram)

Answer:

> Universal Pictures

Contexts:

- Context `ares_doc_8227939188793834871_2`:

```text
Electromyography (EMG) is an electrodiagnostic medicine technique for evaluating and recording the electrical activity produced by skeletal muscles. EMG is performed using an instrument called an electromyograph to produce a record called an electromyogram. An electromyograph detects the electric potential generated by muscle cells when these cells are electrically or neurologically activated. The signals can be analyzed to detect medical abnormalities, activation level, or recruitment order, or to analyze the biomechanics of human or animal movement.
```

## 82. `ares_nq_example_5682352906951331542`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who invented the cornell method of note taking

Answer:

> The Lykan Hypersport

Contexts:

- Context `ares_doc_5682352906951331542`:

```text
The Cornell Notes system (also Cornell note-taking system, Cornell method, or Cornell way) is a note-taking system devised in the 1940s by Walter Pauk, an education professor at Cornell University. Pauk advocated its use in his best-selling book "How to Study in College".
```

## 83. `ares_nq_example_5644676080991349842`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who developed the first printing press in 1430s

Answer:

> Johannes Gutenberg

Contexts:

- Context `ares_doc_5644676080991349842`:

```text
Johannes Gutenberg, a goldsmith by profession, developed, circa 1439, a printing system by adapting existing technologies to printing purposes, as well as making inventions of his own. Printing in East Asia had been prevalent since the Tang dynasty, and in Europe, woodblock printing based on existing screw presses was common by the 14th century. Gutenberg's most important innovation was the development of hand-molded metal printing matrices, thus producing a movable type–based printing press system. His newly devised hand mould made possible the precise and rapid creation of metal movable type in large quantities. Movable type had been hitherto unknown in Europe. In Europe, the two inventions, the hand mould and the printing press, together drastically reduced the cost of printing books and other documents, particularly in short print runs.
```

## 84. `ares_nq_example_7933002036740390435_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> where did the term liberal arts come from

Answer:

> John Roberts

Contexts:

- Context `ares_doc_7933002036740390435_2`:

```text
Rooted in the basic curriculum – the or "education in a circle" – of late Classical and Hellenistic Greece, the "liberal arts" or "liberal pursuits" (Latin ) were already so called in formal education during the Roman Empire. The first recorded use of the term "liberal arts" () occurs in by Marcus Tullius Cicero, but it is unclear if he created the term. Seneca the Younger discusses liberal arts in education from a critical Stoic point of view in "Moral Epistles". The exact classification of the liberal arts varied however in Roman times, and it was only after Martianus Capella in the 5th century AD influentially brought the seven liberal arts as bridesmaids to the "Marriage of Mercury and Philology", that they took on canonical form.
```

## 85. `ares_nq_example_3165901349277199099_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> how many levels of protein structure are there

Answer:

> four

Contexts:

- Context `ares_doc_3165901349277199099_2`:

```text
There are four distinct levels of protein structure.
```

## 86. `ares_nq_example_2223188268381215709_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who presides over the joint sessions of parliament

Answer:

> Theodore Roosevelt

Contexts:

- Context `ares_doc_2223188268381215709_2`:

```text
The joint sitting of the Parliament is called by the President (Article 108) and is presided over by the Speaker or, in his absence, by the Deputy Speaker of the Lok Sabha or in his absence, the Deputy-Chairman of the Rajya Sabha. The Chairman doesn't preside over the joint session at any means/cost.
```

## 87. `ares_nq_example_4245798066923223457`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who has the most all star mvp awards

Answer:

> 4 January 2011

Contexts:

- Context `ares_doc_4245798066923223457`:

```text
Bob Pettit and Kobe Bryant are the only two players to win the All-Star Game MVP four times. Oscar Robertson, Michael Jordan, Shaquille O'Neal, and LeBron James have each won the award three times, while Bob Cousy, Julius Erving, Isiah Thomas, Magic Johnson, Karl Malone, Allen Iverson, Russell Westbrook, and Kevin Durant have all won the award twice. James' first All-Star MVP in 2006 made him the youngest to have ever won the award at the age of 21 years, 1 month. Kyrie Irving, winner of the 2014 All-Star Game MVP, is the second-youngest at 21 years, 10 months. They are notable as being the two youngest to win the award, both as Cleveland Cavaliers. Four of the games had joint winners—Elgin Baylor and Pettit in 1959, John Stockton and Malone in 1993, O'Neal and Tim Duncan in 2000, and O'Neal and Bryant in 2009. O'Neal became the first player in All-Star history to share two MVP awards as well as the first player to win the award with multiple teams. The Los Angeles Lakers have had eleven winners while the Boston Celtics have had eight. Duncan of the U.S. Virgin Islands and Irving of Australia are the only winners not born in the United States. Both Duncan and Irving are American citizens, but are considered "international" players by the NBA because they were not born in one of the fifty states or Washington, D.C. No player trained entirely outside the U.S. has won the award; Irving lived in the U.S. since age two, and Duncan played U.S. college basketball at Wake Forest.
```

## 88. `ares_nq_example_8034580104224221816`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who plays nathan's mother on general hospital

Answer:

> Donna Mills

Contexts:

- Context `ares_doc_8034580104224221816`:

```text
Detective Nathan West arrives in Port Charles, and meets Maxie Jones (Kirsten Storms) when he sublets her apartment. Maxie leaves on a vacation, while Nathan settles in Port Charles. He starts investigating Dr. Silas Clay (Michael Easton) in regards to the overdose of Silas' wife, Nina Reeves (Michelle Stafford), suspecting Silas is responsible. It's later revealed that Nathan is actually Nina's brother. Nathan's mother Madeline Reeves (Donna Mills) claims that Nina has died after Silas has relinquished his rights to Nina's vast estate. Nathan is shocked when Madeline falls into the trap to catch the killer, and confesses that she drugged Nina to kill her unborn child. He arrests Madeline, and simultaneously reveals his identity. Maxie returns with her new manipulative boyfriend Levi Dunkleman (Zachary Garred), who Nathan immediately clashes with.
```

## 89. `ares_nq_example_9078934592669508929_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when did the black death end in england

Answer:

> milling

Contexts:

- Context `ares_doc_9078934592669508929_2`:

```text
During the first half of 1349 the Black Death spread northwards. A second front opened up when the plague arrived by ship at the Humber, after which it spread both south and north. In May it reached York, and during the summer months of June, July and August, it ravaged the north. Certain northern counties, like Durham and Cumberland, had been the victim of violent incursions from the Scots, and were therefore left particularly vulnerable to the devastations of the plague. Pestilence is less virulent during the winter months, and spreads less rapidly. The Black Death in England had survived the winter of 1348–49, but during the following winter it gave in, and by December 1349 conditions were returning to relative normality. It had taken the disease approximately 500 days to traverse the entire country.
```

## 90. `ares_nq_example_6745303307988470742`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> what type of fuel goes in a zippo

Answer:

> 13 February 2018

Contexts:

- Context `ares_doc_6745303307988470742`:

```text
In 2002, Zippo expanded its product line to include a variety of utility-style multi-purpose lighters, known as Zippo MPLs. This was followed in 2005 with the Outdoor Utility Lighter, known as the OUL. These lighters are fueled with butane. In August 2007, Zippo released a new butane lighter called the Zippo BLU.
```

## 91. `ares_nq_example_7750414429766802805_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> what does g stand for in ncis los angeles

Answer:

> Grisha

Contexts:

- Context `ares_doc_7750414429766802805_2`:

```text
G. Callen (born: Grisha Aleksandrovich Nikolaev) is a fictional character in the show "" portrayed by Chris O'Donnell. He is an NCIS Special Agent in Charge, and the senior agent assigned to the Office of Special Projects. O'Donnell made his first appearance during "NCIS" sixth-season episode "Legend (Part 1)".
```

## 92. `ares_nq_example_8437192694659989578`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who played shmuel in the boy in the striped pyjamas

Answer:

> Jack Scanlon

Contexts:

- Context `ares_doc_8437192694659989578`:

```text
The Boy in the Striped Pyjamas (released as The Boy in the Striped Pajamas in the United States) is a 2008 historical tragedy film set in World War II, based on John Boyne's 2006 novel of the same name. Written and Directed by Mark Herman, produced by BBC Films and Heyday Films, and distributed by Miramax, the film stars Vera Farmiga, David Thewlis, Asa Butterfield, and Jack Scanlon. It was released on 12 September 2008 in the United Kingdom.
```

## 93. `ares_nq_example_8052136860650205450_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who wrote the song rainy days and mondays

Answer:

> Proposition 103

Contexts:

- Context `ares_doc_8052136860650205450_2`:

```text
The song was composed in 1971 by the then fairly unknown composers Roger Nichols and Paul Williams. It was released as the first track on the album "Carpenters", popularly known as the Tan Album, and the B-side on the single is "Saturday", written and sung by Richard Carpenter.
```

## 94. `ares_nq_example_4086158102790148091_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who sings i want to dance with you

Answer:

> Montesquieu in the Enlightenment

Contexts:

- Context `ares_doc_4086158102790148091_2`:

```text
"I Just Want to Dance with You" is a song written by John Prine and Roger Cook, and performed by American country music singer George Strait. It was released in April 1998 as the first single to his album, "One Step at a Time", it is his 34th Number One single on the "Billboard" Hot Country Singles & Tracks chart, and his 42nd Number One single when all major trade charts are counted. Prine recorded it 12 years earlier, for his 1986 album "German Afternoons".
```

## 95. `ares_nq_example_907238223200158003_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when did first fast and furious come out

Answer:

> treats

Contexts:

- Context `ares_doc_907238223200158003_2`:

```text
The first film was released in 2001, which began the original trilogy of films focused on racing, and culminated in the standalone film "" (2006). The series then went under a soft reboot with "Fast & Furious" (2009), which transitioned the series toward heists and spying, and concluded with "The Fate of the Furious" (2017). Two final films are planned, and are set to be released in 2020, and 2021, respectively.
```

## 96. `ares_nq_example_6969539427365218166_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who was the top scorer in 2014 world cup

Answer:

> James Rodríguez

Contexts:

- Context `ares_doc_6969539427365218166_2`:

```text
James Rodríguez was awarded the Golden Boot for scoring six goals, the first time that a Colombian player received the award.
```

## 97. `ares_nq_example_8982983311407124347_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> which hormone is released from the ruptured follicle or corpus luteum

Answer:

> estrogen

Contexts:

- Context `ares_doc_8982983311407124347_2`:

```text
The corpus luteum is colored as a result of concentrating carotenoids (including lutein) from the diet and secretes a moderate amount of estrogen that inhibits further release of gonadotropin-releasing hormone (GnRH) and thus secretion of luteinizing hormone (LH) and follicle-stimulating hormone (FSH). A new corpus luteum develops with each menstrual cycle.
```

## 98. `ares_nq_example_5150934530929664244`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who led the conquest of the incas in south america

Answer:

> 1984

Contexts:

- Context `ares_doc_5150934530929664244`:

```text
The Spanish conquest of Peru was one of the most important campaigns in the Spanish colonization of the Americas. After years of preliminary exploration and military skirmishes, 168 Spanish soldiers under conquistador Francisco Pizarro, his brothers, and their native allies captured the Sapa Inca Atahualpa in the 1532 Battle of Cajamarca. It was the first step in a long campaign that took decades of fighting but ended in Spanish victory in 1572 and colonization of the region as the Viceroyalty of Peru. The conquest of the Inca Empire (called "Tahuantinsuyu" or "Tawantinsuyu" in Quechua, meaning "Realm of the Four Parts"), led to spin-off campaigns into present-day Chile and Colombia, as well as expeditions towards the Amazon Basin.
```

## 99. `ares_nq_example_8579271792005383992`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> referring to the organs of reproduction is called

Answer:

> Universal Pictures and Focus Features

Contexts:

- Context `ares_doc_8579271792005383992`:

```text
BULLET::::- Reproductive system: the sex organs, such as ovaries, fallopian tubes, uterus, vulva, vagina, testes, vas deferens, seminal vesicles, prostate and penis.
```

## 100. `ares_nq_example_6050703859996827650`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who is the book of galatians written to

Answer:

> tabby

Contexts:

- Context `ares_doc_6050703859996827650`:

```text
Paul's letter is addressed "to the churches of Galatia" (), but the location of these churches is a matter of debate. A minority of scholars have argued that the "Galatia" is an ethnic reference to a Celtic people living in northern Asia Minor, but most agree that it is a geographical reference to the Roman province in central Asia Minor, which had been settled by immigrant Celts in the 270s BC and retained Gaulish features of culture and language in Paul's day. Acts of the Apostles records Paul traveling to the "region of Galatia and Phrygia", which lies immediately west of Galatia.
```

## 101. `ares_nq_example_6092484764352801171`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> which songs did liam write as you were

Answer:

> Portugal . The Man

Contexts:

- Context `ares_doc_6092484764352801171`:

```text
The album was announced in June 2017 with the release of the single "Wall of Glass". Gallagher also revealed that he would launch his first solo tour of the United States and Canada to support the album's release. Once he completed the lyrics, Liam told NME that he cried his eyes out and thought 'I'm back'. The album's title comes from the sign-off Gallagher typically uses for his Twitter posts. Gallagher worked with producers Greg Kurstin, Andrew Wyatt and Dan Grech-Marguerat on the album, with Kurstin producing the tracks "Wall of Glass", "Paper Crown", "Come Back to Me", and "Doesn't Have to Be That Way", Wyatt producing "Chinatown", and Grech-Marguerat producing the remaining tracks.
```

## 102. `ares_nq_example_4606135189354740425_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when did the ottoman empire surrender in ww1

Answer:

> spontaneously

Contexts:

- Context `ares_doc_4606135189354740425_2`:

```text
The Ottoman Empire participated in World War I as one of the Central Powers. The Ottoman Empire entered the war by carrying out a surprise attack on Russia's Black Sea coast on 29 October 1914, with Russia responding by declaring war on 5 November 1914. Ottoman forces fought the Entente in the Balkans and the Middle Eastern theatre of World War I. The Ottoman Empire's defeat in the war in 1918 was crucial in the eventual dissolution of the empire in 1921.
```

## 103. `ares_nq_example_4791954452980353113`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when does i'm a celebrity get me out of here start in the uk

Answer:

> some other elements

Contexts:

- Context `ares_doc_4791954452980353113`:

```text
The programme's first series debuted on 25 August 2002, and was produced by both LWT and Granada Television, and filmed within Tully, Queensland. Later series were undertaken by ITV Studios, and filmed around Murwillumbah, New South Wales. Celebrities participating on the programme receive a donation from ITV to a charity they nominate, with the money raised from charges on voting via text, phone or interactive services. Each series is hosted by Anthony McPartlin and Declan Donnelly, with the exception of the eighteenth series, in which McPartlin suspended his TV duties for a year in 2018, leaving Donnelly to be joined by Holly Willoughby.
```

## 104. `ares_nq_example_411416507693122968`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> bacterial cell walls are made rigid by the presence of

Answer:

> Peptidoglycan

Contexts:

- Context `ares_doc_411416507693122968`:

```text
Peptidoglycan
```

## 105. `ares_nq_example_3182507307097242113_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who was involved in the mapp vs ohio case

Answer:

> medieval

Contexts:

- Context `ares_doc_3182507307097242113_2`:

```text
Mapp v. Ohio, 367 U.S. 643 (1961), was a landmark case in criminal procedure, in which the United States Supreme Court decided that evidence obtained in violation of the Fourth Amendment, which protects against "unreasonable searches and seizures," may not be used in state law criminal prosecutions in state courts, as well as in federal criminal law prosecutions in federal courts as had previously been the law. The Supreme Court accomplished this by use of a principle known as selective incorporation; in "Mapp" this involved the incorporation of the provisions, as interpreted by the Court, of the Fourth Amendment which is applicable only to actions of the federal government into the Fourteenth Amendment due process clause which is applicable to actions of the states. Dollree Mapp was backed by Don King.
```

## 106. `ares_nq_example_7555953957057409422`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who plays sven in the santa clarita diet

Answer:

> Leo Howard

Contexts:

- Context `ares_doc_7555953957057409422`:

```text
BULLET::::- Leo Howard as Sven, a student who asked Abby out in Season 2 after the tray incident, hurting Eric's feelings
```

## 107. `ares_nq_example_5640132611260516163`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when does panic at the disco album come out

Answer:

> December 15 , 2017

Contexts:

- Context `ares_doc_5640132611260516163`:

```text
On December 15, 2017, the band released their fourth live album "All My Friends We're Glorious: Death of a Bachelor Tour Live". It was released as a limited-edition double-vinyl and digital download. Five days later, the band released a non-album Christmas song titled "Feels Like Christmas." On December 27, bassist Dallon Weekes officially announced his departure from Panic! at the Disco after over eight years of performing in the band, subsequently shifting his focus as the frontman of the band I Don't Know How But They Found Me. On March 19, 2018, the band played a surprise show in Cleveland, Ohio with new touring bassist, Nicole Row. On March 21, 2018, the band released two new songs "Say Amen (Saturday Night)" and "(Fuck A) Silver Lining." At the same time, the band also announced the Pray for the Wicked Tour and a new album called "Pray for the Wicked".
```

## 108. `ares_nq_example_8947071197382617621`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when did dragon ball z air in australia

Answer:

> Fall 1998

Contexts:

- Context `ares_doc_8947071197382617621`:

```text
"Dragon Ball Z" originally aired on the British Comedy Network in Fall 1998.
```

## 109. `ares_nq_example_5406271458964804846_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> deep water fishing boat with many baited hooks

Answer:

> Longline fishing

Contexts:

- Context `ares_doc_5406271458964804846_2`:

```text
Longline fishing
```

## 110. `ares_nq_example_8958554260105256647`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who has the most number one single hits

Answer:

> September 2014

Contexts:

- Context `ares_doc_8958554260105256647`:

```text
† The Beatles are the only act in history to have three consecutive, self-replacing #1s.
```

## 111. `ares_nq_example_6542642245388793003`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> where was the tv show in the heat of the night filmed

Answer:

> Covington , Georgia

Contexts:

- Context `ares_doc_6542642245388793003`:

```text
Like the original movie, the television series also took place in a fictionalized version of Sparta, Mississippi. While there is a real Sparta, the version of Sparta shown on television is very different from the real town. For example, the TV Sparta is situated along Interstate 20, while the real town is nowhere near any interstate. During the first season, Hammond, Louisiana was the site of the show's production. In the second season, the show was moved to Georgia, to an area east of Atlanta and it remained there for the rest of its run. The principal area of Sparta was in fact downtown Covington, Georgia. Rural scenes were filmed in a wide surrounding area, in the Georgia counties of Newton (where Covington is located), Rockdale, Walton, Morgan, and Jasper. Decatur in Dekalb County was used as a stand-in for an episode as the Mississippi Capital city of Jackson, and Atlanta itself was used in one episode, in which Bubba worked on a case there. In fact, during the series' run, many of the cast members had homes in the area and were often spotted in local restaurants and retail stores. The cast members would also go around to local schools to speak to students.
```

## 112. `ares_nq_example_2010294071842366580_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who wrote the treasure of the sierra madre

Answer:

> 22 July 1947

Contexts:

- Context `ares_doc_2010294071842366580_2`:

```text
The Treasure of the Sierra Madre (originally titled Der Schatz der Sierra Madre) is a 1927 adventure novel by bilingual German author B. Traven, whose identity remains unknown. In the book, two destitute American men in Mexico of the 1920s join an older American prospector in a search for gold. John Huston adapted the book as a 1948 film of the same name.
```

## 113. `ares_nq_example_5980486301760893723`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> what is the female lion called in lion king

Answer:

> Joaquin Phoenix

Contexts:

- Context `ares_doc_5980486301760893723`:

```text
Simba (voiced by Matthew Broderick as adult Simba in the films; Jonathan Taylor Thomas as Simba when he is a cub in "The Lion King"; Matt Weinberg as Simba when he is a cub in "The Lion King 1½"; Cam Clarke in "Timon & Pumbaa"; Rob Lowe in "The Lion Guard"; in the live action film Donald Glover as adult Simba and JD McCrary voices Simba when he is a cub) is the son of Mufasa and Sarabi, Scar's nephew, Nala's mate, and Kiara and Kion's father. After defeating Scar, Simba takes Mufasa's place as King of Pride Rock before marrying Nala and having Kiara and Kion with her.
```

## 114. `ares_nq_example_6284503594240226071_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who formed and first came to the colony of maryland

Answer:

> 283,846

Contexts:

- Context `ares_doc_6284503594240226071_2`:

```text
The recorded history of Maryland dates back to the beginning of European exploration, starting with the Venetian John Cabot, who explored the coast of North America for the Kingdom of England in 1498. After European settlements had been made to the south and north, the colonial Province of Maryland was granted by King Charles I to Sir George Calvert (1579–1632), his former Secretary of State in 1632, for settlement beginning in March 1634. It was notable for having been established with religious freedom for Roman Catholics, since Calvert had publicly converted to that faith. Like other colonies and settlements of the Chesapeake Bay region, its economy was soon based on tobacco as a commodity crop, highly prized among the English, cultivated primarily by African slave labor, although many young people came from Britain sent as indentured servants or criminal prisoners in the early years.
```

## 115. `ares_nq_example_972568347460262100_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when was nepal declared a secular state in bs

Answer:

> E-8s senior chief petty officer

Contexts:

- Context `ares_doc_972568347460262100_2`:

```text
Nepal is a secular state under the Constitution Of Nepal 2015, which was promulgated on September 20 , 2015. The Constitution provides for freedom to practice one's religion. The Constitution also specifically denies the right to convert another person. The now-defunct constitution of 1990, which was in effect until January 15, 2007, described the country as a "Hindu Kingdom," although it did not establish Hinduism as the state religion. The Government generally did not interfere with the practice of other religious groups, and religious tolerance was broadly observed; however, there were some restrictions.
```

## 116. `ares_nq_example_2485791396969793161`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when did the song the joker come out

Answer:

> 1973

Contexts:

- Context `ares_doc_2485791396969793161`:

```text
"The Joker" is a song by the Steve Miller Band from their 1973 album "The Joker". It is one of two Steve Miller Band songs that feature the nonce word "pompatus". The song topped the US "Billboard" Hot 100 in early 1974.
```

## 117. `ares_nq_example_54130238553389967_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> what type of tale is the pardoner's tale

Answer:

> Ole Einar Bjørndalen

Contexts:

- Context `ares_doc_54130238553389967_2`:

```text
The tale itself is an extended exemplum. Setting out to kill Death, three young men encounter an Old Man who says they will find him under a nearby tree. When they arrive they discover a hoard of treasure and decide to stay with it until nightfall and carry it away under cover of darkness. Out of greed, they murder one another. The tale and prologue are primarily concerned with what the Pardoner says is his "theme": "Radix malorum est cupiditas" ("Greed is the root of [all] evils").
```

## 118. `ares_nq_example_6378606982206312510`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when is the last time the dolphins went to the superbowl

Answer:

> Super Bowl XIX

Contexts:

- Context `ares_doc_6378606982206312510`:

```text
The team made its first Super Bowl appearance in Super Bowl VI, losing to the Dallas Cowboys, 24–3. The following year, the Dolphins completed the NFL's only perfect season, culminating in a Super Bowl win, winning all 14 of their regular season games, and all three of their playoff games, including Super Bowl VII. They were the third NFL team to accomplish a perfect regular season. The next year, the Dolphins won Super Bowl VIII, becoming the first team to appear in three consecutive Super Bowls, and the second team (the first AFL/AFC team) to win back-to-back championships. Miami also appeared in Super Bowl XVII and Super Bowl XIX, losing both games.
```

## 119. `ares_nq_example_1163524811252371834`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who played the girl in my two dads

Answer:

> 10 May 1940

Contexts:

- Context `ares_doc_1163524811252371834`:

```text
Staci Keanan
```

## 120. `ares_nq_example_4227398832220654666`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> mount everest is part of what mountain range

Answer:

> Himalayas

Contexts:

- Context `ares_doc_4227398832220654666`:

```text
Mount Everest (Nepali: Sagarmatha ; Tibetan: Chomolungma ; Chinese Zhumulangma ) is Earth's highest mountain above sea level, located in the Mahalangur Himal sub-range of the Himalayas. The international border between Nepal (Province No. 1) and China (Tibet Autonomous Region) runs across its summit point.
```

## 121. `ares_nq_example_7475061672965272250_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who was the leader of the soviet union when the berlin wall was built

Answer:

> California

Contexts:

- Context `ares_doc_7475061672965272250_2`:

```text
The transcript of a telephone call between Nikita Khrushchev and Ulbricht, on 1 August in the same year, suggests that the initiative for the construction of the Wall came from Khrushchev. However, other sources suggest that Khrushchev had initially been wary about building a wall, fearing negative Western reaction. Nevertheless, Ulbricht had pushed for a border closure for quite some time, arguing that East Germany's very existence was at stake.
```

## 122. `ares_nq_example_2362041234838636399_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who was the first coronated king of manipur at kangla

Answer:

> Pakhangba

Contexts:

- Context `ares_doc_2362041234838636399_2`:

```text
In ancient times, 'Kangla' was the royal palace since the reign of Pakhangba who ascended the throne in 20,000 BC according to Wakoklon Heelel Thilel Salai Amai Eelon Pukok PuYa, the true Lailik of Kangleipak written by ꯃꯥꯏꯆꯧ.
```

## 123. `ares_nq_example_6651255565624706987_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> where do secondary xylem and phloem cells arise from

Answer:

> The vascular cambium

Contexts:

- Context `ares_doc_6651255565624706987_2`:

```text
The vascular cambium is the main growth tissue in the stems and roots of many plants, specifically in dicots such as buttercups and oak trees, gymnosperms such as pine trees, as well as in certain vascular plants. It produces secondary xylem inwards, towards the pith, and secondary phloem outwards, towards the bark. In herbaceous plants, it occurs in the vascular bundles which are often arranged like beads on a necklace forming an interrupted ring inside the stem. In woody plants, it forms a cylinder of unspecialized meristem cells, as a continuous ring from which the new tissues are grown. Unlike the xylem and phloem, it does not transport water, minerals or food through the plant. Other names for the vascular cambium are the main cambium, wood cambium, or bifacial cambium.
```

## 124. `ares_nq_example_927966355158112429_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> the group that officially elects the president of the united states is called

Answer:

> First Lieutenant Israel Greene

Contexts:

- Context `ares_doc_927966355158112429_2`:

```text
The election of the president and the vice president of the United States is an indirect election in which citizens of the United States who are registered to vote in one of the 50 U.S. states or in Washington, D.C. cast ballots not directly for those offices, but instead for members of the U.S. Electoral College, known as electors. These electors then in turn cast direct votes, known as electoral votes, for president, and for vice president. The candidate who receives an absolute majority of electoral votes (at least 270 out of a total of 538, since the Twenty-Third Amendment granted voting rights to citizens of Washington, D.C.) is then elected to that office. If no candidate receives an absolute majority of the votes for President, the House of Representatives chooses the winner; if no one receives an absolute majority of the votes for Vice President, then the Senate chooses the winner.
```

## 125. `ares_nq_example_3654809363614635590`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who played tibbs on in the heat of the night

Answer:

> the 1940s

Contexts:

- Context `ares_doc_3654809363614635590`:

```text
Howard Ellsworth Rollins Jr. (October 17, 1950 – December 8, 1996) was an American stage, film and television actor. Howard Rollins was best known for his role as Andrew Young in 1978's "King", George Haley in the 1979 miniseries "", Coalhouse Walker Jr. in the 1981 film "Ragtime", Captain Davenport in the 1984 film "A Soldier's Story", and as Virgil Tibbs on the TV crime drama "In the Heat of the Night".
```

## 126. `ares_nq_example_1615626468308135253`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> what is one element a topographic map shows

Answer:

> relief

Contexts:

- Context `ares_doc_1615626468308135253`:

```text
In modern mapping, a topographic map is a type of map characterized by large-scale detail and quantitative representation of relief, usually using contour lines, but historically using a variety of methods. Traditional definitions require a topographic map to show both natural and man-made features. A topographic survey is typically published as a map series, made up of two or more map sheets that combine to form the whole map. A contour line is a line connecting places of equal elevation.
```

## 127. `ares_nq_example_3895386769528538506_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who played the twins in darling buds of may

Answer:

> 1996

Contexts:

- Context `ares_doc_3895386769528538506_2`:

```text
BULLET::::- Christina Giles, as Petunia Larkin, twin sister to Zinnia (18 episodes)
```

## 128. `ares_nq_example_8972183967530424533_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> the cuban revolt against spain was led by

Answer:

> Máximo Gomez

Contexts:

- Context `ares_doc_8972183967530424533_2`:

```text
Martí was killed shortly after landing on May 19, 1895, at Dos Rios, but Máximo Gomez and Antonio Maceo fought on, taking the war to all parts of Oriente. By the end of June, all of Camagüey was at war. Based on new research in Cuban sources, historian John Lawrence Tone demonstrated that Gomez and Maceo were the first to force the civilian forces to choose sides. "Either they relocated to the east side of the islands, where the Cubans controlled the mountainous terrain, or they would be accused of supporting the Spanish and be subject to immediate trial and execution." Continuing west, they were joined by 1868 war veterans, such as Polish internationalist General Carlos Roloff and Serafín Sánchez in Las Villas, who brought weapons, men and experience to the revolutionaries' arsenal.
```

## 129. `ares_nq_example_2520046502679470257_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who designed the earth day flag in 1969

Answer:

> John McConnell

Contexts:

- Context `ares_doc_2520046502679470257_2`:

```text
Section::::John McConnell's "Earth Day" flag.
```

## 130. `ares_nq_example_5007497922163706548`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who negotiated an agreement with japan concerning the future of korea

Answer:

> the Franciscan order

Contexts:

- Context `ares_doc_5007497922163706548`:

```text
Following Imperial Japan’s victory in the Russo-Japanese War, with its subsequent withdrawal of Russian influence, and the Taft–Katsura Agreement, in which the United States allegedly agreed not to interfere with Japan in matters concerning Korea, the Japanese government sought to formalize its sphere of influence over the Korean Peninsula.
```

## 131. `ares_nq_example_6553353802049563745_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when did the twenty one pilots hiatus start

Answer:

> July 2017

Contexts:

- Context `ares_doc_6553353802049563745_2`:

```text
In an interview with "Alternative Press" in November 2016, Twenty One Pilots stated that after their last show, they will be "going dark" to focus on new music. Joseph stated that he would like to focus on lyrical content of the music, and bring the music back to the "authenticity, lyrics, delivery, and fearlessness of songwriting" similar to that of the self-titled album. The band's last activity came in July 2017 in the form of posts on social media depicting an eye closing over lyrics from several of their songs.
```

## 132. `ares_nq_example_467684233955454366`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> what are the 4 types of nitrogenous bases

Answer:

> adenine ( A )

Contexts:

- Context `ares_doc_467684233955454366`:

```text
In the biological sciences, nitrogenous bases are increasingly termed nucleobases because of their role in nucleic acids - their flat shape is particularly important when considering their roles as the building blocks of DNA and RNA. A set of five nitrogenous bases is used in the construction of nucleotides, which in turn build up nucleic acids like DNA and RNA. These nitrogenous bases are adenine (A), uracil (U), guanine (G), thymine (T), and cytosine (C). Thymine and uracil are distinguished by merely the presence or absence of a methyl group on the fifth carbon (C5) of these heterocyclic six-membered rings. The nitrogenous bases form hydrogen bonds between opposing DNA strands to form the rungs of the "twisted ladder" or double helix of DNA or a biological catalyst that is found in the nucleotides. Adenine is always paired with thymine, and guanine is always paired with cytosine. These are known as base pairs. Adenine forms two hydrogen bonds with thymine in DNA and two hydrogen bonds with uracil in RNA, while three hydrogen bonds are formed between guanine and cytosine. There are a variety of other non-canonical base pairs that occur in nature due to the versatility of these molecular structures. Uracil is only present in RNA, replacing thymine. Pyrimidines include thymine, cytosine, and uracil. They have a single ring structure. Purines include adenine and guanine. They have a double ring structure.
```

## 133. `ares_nq_example_7236492039847101221_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when did they start adding zinc to pennies

Answer:

> Confederate victory

Contexts:

- Context `ares_doc_7236492039847101221_2`:

```text
Bronze, 1909–1942. Initially the alloy of the Lincoln cent followed that established for this denomination with the Indian Head design in 1864, 95% copper and 2.5% tin and 2.5% zinc.
```

## 134. `ares_nq_example_6770911139022104689`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> which president supported the creation of the environmental protection agency (epa)

Answer:

> Richard Nixon

Contexts:

- Context `ares_doc_6770911139022104689`:

```text
The Environmental Protection Agency (EPA) is an independent agency of the United States federal government for environmental protection. President Richard Nixon proposed the establishment of EPA on July 9, 1970 and it began operation on December 2, 1970, after Nixon signed an executive order. The order establishing the EPA was ratified by committee hearings in the House and Senate. The agency is led by its Administrator, who is appointed by the President and approved by Congress. The current Administrator is former Deputy Administrator Andrew R. Wheeler, who had been acting administrator since July 2018. The EPA is not a Cabinet department, but the Administrator is normally given cabinet rank.
```

## 135. `ares_nq_example_2485791396969793161_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when did the song the joker come out

Answer:

> 31 December 1960

Contexts:

- Context `ares_doc_2485791396969793161_2`:

```text
"The Joker" is a song by the Steve Miller Band from their 1973 album "The Joker". It is one of two Steve Miller Band songs that feature the nonce word "pompatus". The song topped the US "Billboard" Hot 100 in early 1974.
```

## 136. `ares_nq_example_1281705529368409187`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> band who had a hit with heart and soul crossword

Answer:

> British pop band T'Pau

Contexts:

- Context `ares_doc_1281705529368409187`:

```text
"Heart and Soul" is a song by British pop band T'Pau. Featuring vocalist Carol Decker, the song was released as the group's first single in 1987 from their debut album "Bridge of Spies". Following its inclusion in a Pepe Jeans advert, the single reached No. 4 in both the US and UK charts.
```

## 137. `ares_nq_example_9070003128797416503_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who has scored the most half centuries in test cricket

Answer:

> Sachin Tendulkar

Contexts:

- Context `ares_doc_9070003128797416503_2`:

```text
The trend of countries to increase the number of Test matches they play means that the aggregate lists are dominated by modern players. Sri Lankan spinner Muttiah Muralitharan became the highest Test wicket-taker in December 2007, when he passed Shane Warne's total of 708 wickets. Within a year, the equivalent batting record of highest run-scorer had also changed hands: Sachin Tendulkar surpassed the tally of 11,953 runs by Brian Lara. The record for most dismissals by a wicket-keeper is held by Mark Boucher of South Africa while the record for most catches by a fielder is held by Rahul Dravid.
```

## 138. `ares_nq_example_7615960389617916651_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who wrote the song be thankful for what you got

Answer:

> William DeVaughn

Contexts:

- Context `ares_doc_7615960389617916651_2`:

```text
"Be Thankful for What You Got" is a soul song written and first performed by William DeVaughn.
```

## 139. `ares_nq_example_1609362606908546787`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when does the cannes film festival take place

Answer:

> usually in May

Contexts:

- Context `ares_doc_1609362606908546787`:

```text
The Cannes Festival (; ), until 2002 called the International Film Festival (') and known in English as the Cannes Film Festival, is an annual film festival held in Cannes, France, which previews new films of all genres, including documentaries from all around the world. Founded in 1946, the invitation-only festival is held annually (usually in May) at the Palais des Festivals et des Congrès.
```

## 140. `ares_nq_example_217684522847197793_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when does body temperature tend to be lowest

Answer:

> Venkaiah Naidu

Contexts:

- Context `ares_doc_217684522847197793_2`:

```text
In humans, a diurnal variation has been observed dependent on the periods of rest and activity, lowest at 11 p.m. to 3 a.m. and peaking at 10 a.m. to 6 p.m. Monkeys also have a well-marked and regular diurnal variation of body temperature that follows periods of rest and activity, and is not dependent on the incidence of day and night; nocturnal monkeys reach their highest body temperature at night and lowest during the day. Sutherland Simpson and J.J. Galbraith observed that all nocturnal animals and birds – whose periods of rest and activity are naturally reversed through habit and not from outside interference – experience their highest temperature during the natural period of activity (night) and lowest during the period of rest (day). Those diurnal temperatures can be reversed by reversing their daily routine.
```

## 141. `ares_nq_example_5083423407995797659_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when did they start vaccinating for whooping cough

Answer:

> the 1940s

Contexts:

- Context `ares_doc_5083423407995797659_2`:

```text
An estimated 16.3 million people worldwide were infected in 2015. Most cases occur in the developing world, and people of all ages may be affected. In 2015, pertussis resulted in 58,700 deaths – down from 138,000 deaths in 1990. Outbreaks of the disease were first described in the 16th century. The bacterium that causes the infection was discovered in 1906. The pertussis vaccine became available in the 1940s.
```

## 142. `ares_nq_example_6563592320308552203_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> what is the wave length of x rays

Answer:

> February 14 , 2015

Contexts:

- Context `ares_doc_6563592320308552203_2`:

```text
X-rays make up X-radiation, a form of high-energy electromagnetic radiation. Most X-rays have a wavelength ranging from 0.01 to 10 nanometers, corresponding to frequencies in the range 30 petahertz to 30 exahertz (3×10 Hz to 3×10 Hz) and energies in the range 100 eV to 100 keV. X-ray wavelengths are shorter than those of UV rays and typically longer than those of gamma rays. In many languages, X-radiation is referred to as Röntgen radiation, after the German scientist Wilhelm Röntgen who discovered it on November 8, 1895. He named it "X-radiation" to signify an unknown type of radiation. Spelling of "X-ray(s)" in the English language includes the variants "x-ray(s)", "xray(s)", and "X ray(s)".
```

## 143. `ares_nq_example_1668669287255788257_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who wrote antigone and what are the dates of his birth and death

Answer:

> Inner Circle

Contexts:

- Context `ares_doc_1668669287255788257_2`:

```text
Sophocles
```

## 144. `ares_nq_example_3544151584263258729`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> where was the film manchester by the sea filmed

Answer:

> Manchester

Contexts:

- Context `ares_doc_3544151584263258729`:

```text
Manchester by the Sea (film)
```

## 145. `ares_nq_example_7901746249864619718_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when does the 14th season of grey's anatomy come out

Answer:

> September 28 , 2017

Contexts:

- Context `ares_doc_7901746249864619718_2`:

```text
"Grey's Anatomy" was renewed for a 14th season on February 10, 2017. It premiered on September 28, 2017, with a two-hour premiere. Ellen Pompeo announced that she would be directing several episodes in the 14th season. On April 28, 2017, veteran writer Krista Vernoff announced that she would return to the show as a writer after leaving the show after the seventh season. On January 11, 2018, ABC released a six-episode web series following the new surgical interns at Grey Sloan Memorial Hospital. The web series was written by Barbara Kaye Friend and directed by series regular Sarah Drew.
```

## 146. `ares_nq_example_6395885127392955720_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> where does jack ryan live in patriot games

Answer:

> In 1922

Contexts:

- Context `ares_doc_6395885127392955720_2`:

```text
Ryan was born in 1950 to an Irish Catholic family in Baltimore, Maryland. His father, Emmet William Ryan, was a Baltimore Police Department homicide lieutenant and World War II veteran. The elder Ryan had served with the U.S. Army's 101st Airborne Division at the Battle of the Bulge in western Europe. His mother, Catherine Burke Ryan, was a nurse. "Without Remorse" mentioned that he had a sister, who lived in Seattle. After graduating from Loyola High School (now Loyola Blakefield), a Roman Catholic Jesuit prep school in Towson, Maryland in suburban Baltimore County, Ryan attended Boston College, graduating with a Bachelor of Arts degree in economics (with a strong minor in history) and a commission as a second lieutenant in the U.S. Marine Corps (via Officer Candidate School). While waiting for the Corps to assign him, he passed the Certified Public Accountant exam.
```

## 147. `ares_nq_example_2467509477831469982_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> where is fort myers located at in florida

Answer:

> the breast or lower chest

Contexts:

- Context `ares_doc_2467509477831469982_2`:

```text
Fort Myers or Ft. Myers, is the county seat and commercial center of Lee County, Florida, United States. It has grown rapidly in recent years. As of the 2010 census, the city population was 62,298 and in 2018 was estimated at 82,254.
```

## 148. `ares_nq_example_2855755816946801432`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who starred in the tv show even stevens

Answer:

> Shia LaBeouf

Contexts:

- Context `ares_doc_2855755816946801432`:

```text
The series was produced by Brookwell McNamara Entertainment. It is often recognized as launching Shia LaBeouf's breakout career as an actor. The show also features fast motion photography, which it employs in every episode.
```

## 149. `ares_nq_example_2876182999155230775_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when were 2 dollar bills stopped being made

Answer:

> a cleansing ritual

Contexts:

- Context `ares_doc_2876182999155230775_2`:

```text
The United States two-dollar bill ($2) is a current denomination of U.S. currency. The portrait of Thomas Jefferson, the third President of the United States (1801–09), is featured on the obverse of the note. The reverse features an engraving of the painting "Declaration of Independence" by John Trumbull.
```

## 150. `ares_nq_example_6244540977142172176`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when was the last time it snowed in england on christmas day

Answer:

> Marie Van Brittan Brown

Contexts:

- Context `ares_doc_6244540977142172176`:

```text
Christmas 2009 was a white Christmas in some parts of Britain, with thick lying snow which easterly winds had brought over the previous week. Travel over much of Britain was badly affected by ice and snow on roads, and was made more slippery by partial daytime thaw followed by overnight refreezing. It was the first white Christmas anywhere in the United Kingdom since 2004. There was another white Christmas in 2010, it was also the coldest Christmas Day ever recorded in the United Kingdom. In 2014, parts of the Northern Isles had a white Christmas and again in 2017, Northern England and Southern Scotland had a white Christmas.
```

## 151. `ares_nq_example_8188778280161966817_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> what type of plate boundary is associated with iceland and its volcanic eruptions

Answer:

> every two to six years

Contexts:

- Context `ares_doc_8188778280161966817_2`:

```text
The volcanoes of Iceland include a high concentration of active ones due to Iceland's location on the mid-Atlantic Ridge, a divergent tectonic plate boundary, and its location over a hot spot. The island has 30 active volcanic systems, of which 13 have erupted since the settlement of Iceland in AD 874.
```

## 152. `ares_nq_example_2032750066334794467_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who won so you think you can dance season 13

Answer:

> Bonnie Lipton

Contexts:

- Context `ares_doc_2032750066334794467_2`:

```text
The episode began with a group dance for all the contestants and all-stars that began with the Top 4 contestants waking up and getting ready for the big day. There were also new group dances for the hip-hop finalists and their all-stars; the ballroom finalists and their all-stars; and the contemporary finalists (plus Emma) and their all stars. In addition, there was a new group routine for all the finalists plus Maddie Ziegler, and Cat Deely chose to reprise her favorite all-stars routine. During the course of the broadcast, each of the Top 4 reprised their favorite solo of the season, each judge chose two favorite routines to see again, each of the all-stars chose a favorite duet to reprise, and other duets were reprised as described below. Results were announced during the last hour of the show as follows: Emma placed 4th, Tate was 3rd, J. T. was runner-up, and Kida won the $250,000 top prize and will be featured on the cover of "Dance Spirit" magazine.
```

## 153. `ares_nq_example_2905877218891850711`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> how old do you have to be to get a gun licence in nz

Answer:

> 16 or older

Contexts:

- Context `ares_doc_2905877218891850711`:

```text
BULLET::::- Be 16 or older;
```

## 154. `ares_nq_example_564063817056958231_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when does boomer find out she a cylon

Answer:

> Chelsea

Contexts:

- Context `ares_doc_564063817056958231_2`:

```text
Lieutenant Junior Grade Sharon "Boomer" Valerii is a Cylon sleeper agent programmed with false memories of being raised in the mining colony Troy by parents Katherine and Abraham Valerii, who supposedly died in an accident that wiped out the colony population. Before the mini-series, Boomer and Galen Tyrol are romantically involved, which is against military protocol due to their ranks. Her programming leads her to black out and sabotage the "Galactica" on several occasions, which Tyrol unwittingly abets by hiding evidence implicating her. In "Kobol's Last Gleaming", Commander Adama sends Boomer on a mission to destroy the Cylon basestar orbiting Kobol; and after her return, she shoots Adama twice in the chest, putting him in a coma and revealing her nature to the crew.
```

## 155. `ares_nq_example_1460738236019346895`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> the most common form of megalithic architecture in europe is

Answer:

> the portal tomb

Contexts:

- Context `ares_doc_1460738236019346895`:

```text
The most common type of megalithic construction in Europe is the portal tomb – a chamber consisting of upright stones (orthostats) with one or more large flat capstones forming a roof. Many of these, though by no means all, contain human remains, but it is debatable whether use as burial sites was their primary function. The megalithic structures in the northwest of France are believed to be the oldest in Europe based on radiocarbon dating. Though generally known as "dolmens", the term most accepted by archaeologists is "portal tomb". However many local names exist, such as "anta" in Galicia and Portugal, "stazzone" in Sardinia, "hunebed" in the Netherlands, "Hünengrab" in Germany, "dysse" in Denmark, and "cromlech" in Wales. It is assumed that most portal tombs were originally covered by earthen mounds.
```

## 156. `ares_nq_example_5973003791441271262`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> where does the last name andersen originate from

Answer:

> Danish

Contexts:

- Context `ares_doc_5973003791441271262`:

```text
Andersen () is a Danish-Norwegian patronymic surname meaning "son of Anders" (itself derived from the Greek name "Ανδρέας/Andreas", cf. English Andrew). It is the fifth most common surname in Denmark, shared by about 3.2% of the population.
```

## 157. `ares_nq_example_24224390922062302_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who sang the song oh what a lonely boy

Answer:

> Andrew Gold

Contexts:

- Context `ares_doc_24224390922062302_2`:

```text
Lonely Boy (Andrew Gold song)
```

## 158. `ares_nq_example_4395570541686945657_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who are the dallas cowboys playing on thanksgiving

Answer:

> the eastern Catskill Mountains

Contexts:

- Context `ares_doc_4395570541686945657_2`:

```text
Since 1978, the NFL's Thanksgiving Day games have traditionally included one game hosted by the Detroit Lions, and one game hosted by the Dallas Cowboys. Since 2006, with the advent of the NFL's then-new "Thursday Night Football", a third primetime game has also been played on Thanksgiving; unlike the traditional afternoon doubleheader, this game has no fixed host and has featured different teams annually. In 2012, the primetime game was moved to NBC's "Sunday Night Football" package.
```

## 159. `ares_nq_example_72470187726524890_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> where was part of the classic surfing movie endless summer filmed

Answer:

> pia mater

Contexts:

- Context `ares_doc_72470187726524890_2`:

```text
Filmmaker/narrator Bruce Brown follows two surfers, Mike Hynson and Robert August, on a surfing trip around the world. Despite the balmy climate of their native California, cold ocean currents make local beaches inhospitable during the winter. They travel to the coasts of Australia, New Zealand, Tahiti, Hawaii, Senegal, Ghana, Nigeria and South Africa in a quest for new surf spots and introduce locals to the sport. Other important surfers of the time, such as Miki Dora, Phil Edwards and Butch Van Artsdalen also appear.
```

## 160. `ares_nq_example_6223491322879193188_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> what is the name of the compound p4010

Answer:

> Phosphorus pentoxide

Contexts:

- Context `ares_doc_6223491322879193188_2`:

```text
Phosphorus pentoxide
```

## 161. `ares_nq_example_6621623690879619950_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> the elements in each period have the same number of

Answer:

> Ptolemy

Contexts:

- Context `ares_doc_6621623690879619950_2`:

```text
A period in the periodic table is a row of chemical elements. All elements in a row have the same number of electron shells. Each next element in a period has one more proton and is less metallic than its predecessor. Arranged this way, groups of elements in the same column have similar chemical and physical properties, reflecting the periodic law. For example, the alkali metals lie in the first column (group 1) and share similar properties, such as high reactivity and the tendency to lose one electron to arrive at a noble-gas electronic configuration. As of 2016, a total of 118 elements have been discovered and confirmed.
```

## 162. `ares_nq_example_5078709962400196312_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> what mlb teams did deion sanders play for

Answer:

> New York Yankees

Contexts:

- Context `ares_doc_5078709962400196312_2`:

```text
Deion Luwynn Sanders Sr. (; born August 9, 1967), nicknamed "Prime Time" and "Neon Deion", is a retired American football player and baseball player and sports analyst who played in the National Football League (NFL) for 14 seasons. During his football career, he was a member of the Atlanta Falcons, San Francisco 49ers, Dallas Cowboys, Washington Redskins, and the Baltimore Ravens. He also had a part-time career as a baseball outfielder for nine seasons in Major League Baseball (MLB), where he played professionally for the New York Yankees, the Atlanta Braves, the Cincinnati Reds, and the San Francisco Giants. Sanders won two Super Bowl titles and made one World Series appearance in 1992, making him the only individual to appear in both a Super Bowl and a World Series.
```

## 163. `ares_nq_example_4892429640540595424`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who has made the most premier league appearances

Answer:

> Gareth Barry

Contexts:

- Context `ares_doc_4892429640540595424`:

```text
The first player to reach the milestone was midfielder Gary Speed, in representation of Leeds United, Everton, Newcastle United and Bolton Wanderers; his 500th match was Bolton's 4–0 win over West Ham United on 9 December 2006. Speed held the record for most appearances until 14 February 2009, when goalkeeper David James played his 536th match, for Portsmouth against his former team Manchester City. James ended with 572 appearances, a record which was broken by Ryan Giggs on 14 May 2011, having played all of his matches for Manchester United. On 25 September 2017, Gareth Barry broke Giggs' record by playing his 633rd match, West Bromwich Albion's 2–0 loss at Arsenal. At the time of breaking the record, Barry ranked 8th in English top division appearances since the Second World War, trailing Giggs in 6th (672 total top division appearances) and six other players.
```

## 164. `ares_nq_example_1092628173964573043_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who owns the rights to rocky and bullwinkle

Answer:

> MFSK

Contexts:

- Context `ares_doc_1092628173964573043_2`:

```text
"The Rocky and Bullwinkle Show" remained in syndicated reruns and was still available for local television stations through The Program Exchange as late as 2016; WBBZ-TV, for instance, aired the show in a strip to counterprogram 10 PM newscasts in the Buffalo, New York market during the summer 2013 season. The underlying rights are now owned by Universal Pictures, which holds the library of predecessor companies DreamWorks Animation and Classic Media, and who in turn with copyright holder Ward Productions forms the joint venture Bullwinkle Studios, which manages the Rocky and Bullwinkle properties; Universal's purchase of Classic Media coincided with The Program Exchange's shutdown.
```

## 165. `ares_nq_example_9179702110514757818_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> where are the next two winter olympics going to be held

Answer:

> Pangaea or Pangea

Contexts:

- Context `ares_doc_9179702110514757818_2`:

```text
Five cities have been chosen by the IOC to host upcoming Olympic Games: Tokyo for the 2020 Summer Olympics, Beijing for the 2022 Winter Olympics, Paris for the 2024 Summer Olympics, Milan-Cortina d'Ampezzo for the 2026 Winter Olympics, and Los Angeles for the 2028 Summer Olympics.
```

## 166. `ares_nq_example_1653574612763270615_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> where is thank you for your service based

Answer:

> 1689

Contexts:

- Context `ares_doc_1653574612763270615_2`:

```text
Thank You for Your Service is a 2017 American biographical war drama film written and directed by Jason Hall, in his directorial debut, and based on the 2013 non-fiction book of the same name by David Finkel. Finkel, a "Washington Post" reporter, wrote about veterans of the 2nd Battalion, 16th Infantry Regiment returning to the vicinity of Fort Riley, Kansas, following a 15-month deployment in Iraq in 2007. The film is about posttraumatic stress disorder (PTSD), depicting U.S. soldiers who try to adjust to civilian life, and stars Miles Teller, Haley Bennett, Beulah Koale, Amy Schumer and Scott Haze. Bruce Springsteen wrote a new song, "Freedom Cadence", specifically for the closing credits.
```

## 167. `ares_nq_example_7779530728701828621_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> where did they film the game of thrones

Answer:

> Gareth Barry

Contexts:

- Context `ares_doc_7779530728701828621_2`:

```text
Game of Thrones is an American fantasy drama television series created by David Benioff and D. B. Weiss for HBO. It is an adaptation of "A Song of Ice and Fire", George R. R. Martin's series of fantasy novels, the first of which is "A Game of Thrones". The show was both produced and filmed in Belfast and elsewhere in the United Kingdom. Filming locations also included Canada, Croatia, Iceland, Malta, Morocco, and Spain. The series premiered on HBO in the United States on April 17, 2011, and concluded on May 19, 2019, with 73 episodes broadcast over eight seasons.
```

## 168. `ares_nq_example_9217499733870801634`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> what kind of plate boundary is nepal on

Answer:

> orogenic belt

Contexts:

- Context `ares_doc_9217499733870801634`:

```text
The collision with the Eurasian Plate along the boundary between India and Nepal formed the orogenic belt that created the Tibetan Plateau and the Himalaya Mountains, as sediment bunched up like earth before a plow.
```

## 169. `ares_nq_example_3466298422174960041`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who plays charles on have and have nots

Answer:

> an outer silicate solid crust

Contexts:

- Context `ares_doc_3466298422174960041`:

```text
BULLET::::- Charles Frederickson (Nick Sager): (Season 4–present) The president-elect and the love interest to Candace, whom she uses to help her get her money back. Later down the line Charles finds out about Candace's background but decides to fall in love with her anyway.
```

## 170. `ares_nq_example_1370486447842329054_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who sings i'll sleep when i'm dead

Answer:

> the left coronary artery

Contexts:

- Context `ares_doc_1370486447842329054_2`:

```text
BULLET::::- "I'll Sleep When I'm Dead", a song from "Warren Zevon"
```

## 171. `ares_nq_example_2482202658787537401`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> is a network connection device that can build tables that identify addresses on each network

Answer:

> a router

Contexts:

- Context `ares_doc_2482202658787537401`:

```text
In computer networking a routing table, or routing information base (RIB), is a data table stored in a router or a networked computer that lists the routes to particular network destinations, and in some cases, metrics (distances) associated with those routes. The routing table contains information about the topology of the network immediately around it. The construction of routing tables is the primary goal of routing protocols. Static routes are entries made in a routing table by non-automatic means and which are fixed rather than being the result of some network topology "discovery" procedure.
```

## 172. `ares_nq_example_3359008398677892283_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who was the killer in the movie i know what you did last summer

Answer:

> Ben Willis

Contexts:

- Context `ares_doc_3359008398677892283_2`:

```text
Julie finds an article mentioning Susie's father, Ben Willis, and realizes that Ben was the man they ran over, moments after he had killed David to avenge his daughter. She then goes to the docks to tell Ray, but he refuses to believe her. Julie notices Ray's boat is called "Billy Blue" and runs away. Ben appears, knocking Ray unconscious, and invites Julie to hide on his boat. On the boat, she finds photos and articles about her friends and her, and pictures of Susie. Ben's boat leaves the docks, and he begins tormenting Julie, chasing her below deck; there, she uncovers the bodies of Helen and Barry in the boat's ice box. Ray regains consciousness and steals a motorboat to rescue Julie. He ultimately uses the rigging to sever Ben's hand and send him overboard. When Julie and Ray are questioned by the police, they deny knowing why Ben attempted to kill them, but they are relieved not to have actually killed anyone the previous summer, and reconcile.
```

## 173. `ares_nq_example_8130289504436773028_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who sang theme song for dukes of hazard

Answer:

> 10 June 1940

Contexts:

- Context `ares_doc_8130289504436773028_2`:

```text
The "Theme from "The Dukes of Hazzard" (Good Ol' Boys)" is a song written and recorded by American country music singer Waylon Jennings. It was released in August 1980 as the second single from the album "Music Man". Recognizable to fans as the theme to the CBS comedy adventure television series "The Dukes of Hazzard", the song became a #1 hit on the "Billboard" Hot Country Singles chart in 1980.
```

## 174. `ares_nq_example_1649058525465685033_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> what order do the captain america movies go in

Answer:

> Major General Clarence L. Tinker

Contexts:

- Context `ares_doc_1649058525465685033_2`:

```text
From August 30 to September 6, 2018, in conjunction with Marvel Studios' 10 year anniversary celebrations, all 20 films released at the time ("Iron Man" through "Ant-Man and the Wasp") were screened in IMAX. The films were shown in release order, with four films per day. The final days of the festival were theme related, with one showing "origin" films ("Iron Man", "Spider-Man: Homecoming", "Black Panther", and "Doctor Strange"), one showing "team-ups" ("Guardians of the Galaxy Vol. 2", "Captain America: Civil War", "The Avengers", and "Avengers: Infinity War"), and the final day showing "Iron Man" and "The Avengers" as chosen by the fans via a Twitter poll. The festival also saw "Iron Man", "The Incredible Hulk", and "Captain America: The First Avenger" released in IMAX for the first time.
```

## 175. `ares_nq_example_6101158474661235823`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> creating appropriation bills falls under which power of congress

Answer:

> Kathy Najimy

Contexts:

- Context `ares_doc_6101158474661235823`:

```text
According to the Origination Clause of the United States Constitution, all bills for raising revenue, generally tax bills, must originate in the House of Representatives, similar to the Westminster system requirement that all money bills originate in the lower house. Traditionally, though, appropriation bills also originate in the House of Representatives. House appropriations bills begin with "H.R.", meaning "House of Representatives". In reference to revenue bills, the Constitution also states that the "Senate may propose or concur with Amendments as on other Bills." As with revenue bills, the Senate and House each drafts and considers its own appropriation bill. The Senate then "cuts-and-pastes," substituting the language of its version of a particular appropriation bill for the language of the House bill, then agrees to the bill as amended.
```

## 176. `ares_nq_example_5298560410953979569_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> where does the sweetness of fruit come from

Answer:

> Thomas Lennon

Contexts:

- Context `ares_doc_5298560410953979569_2`:

```text
Fructose
```

## 177. `ares_nq_example_2099882460840294879_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> where did the idea of a unicorn come from

Answer:

> Greek writers of natural history

Contexts:

- Context `ares_doc_2099882460840294879_2`:

```text
Unicorns are not found in Greek mythology, but rather in the accounts of natural history, for Greek writers of natural history were convinced of the reality of unicorns, which they believed lived in India, a distant and fabulous realm for them. The earliest description is from Ctesias, who in his book "Indika" ("On India") described them as wild asses, fleet of foot, having a horn a cubit and a half () in length, and colored white, red and black.
```

## 178. `ares_nq_example_6365160075395818746_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> points outside the production possibilities curve represent combinations of products that are

Answer:

> The Beatles

Contexts:

- Context `ares_doc_6365160075395818746_2`:

```text
Any point that lies either on the production possibilities curve or to the left of it is said to be an attainable point: it can be produced with currently available resources. Points that lie to the right of the production possibilities curve are said to be unattainable because they cannot be produced using currently available resources. Points that lie strictly to the left of the curve are said to be inefficient, because existing resources would allow for production of more of at least one good without sacrificing the production of any other good. An efficient point is one that lies on the production possibilities curve. At any such point, more of one good can be produced only by producing less of the other.
```

## 179. `ares_nq_example_599106694350296477_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> theme of the song roar by katy perry

Answer:

> standing up for oneself

Contexts:

- Context `ares_doc_599106694350296477_2`:

```text
"Roar" is a song by American singer Katy Perry for her fourth studio album, "Prism" (2013). It was released as the lead single from the record on August 10, 2013. Perry co-wrote the song with Bonnie McKee and its producers Dr. Luke, Max Martin, and Cirkut. It is a pop song containing elements of arena rock and lyrics centering on standing up for oneself and self-empowerment.
```

## 180. `ares_nq_example_6971297271942455076`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> in the texas legislature the house has members and the senate has

Answer:

> member

Contexts:

- Context `ares_doc_6971297271942455076`:

```text
The Legislature of the state of Texas is the state legislature of Texas. The legislature is a bicameral body composed of a 31-member Senate and a 150-member House of Representatives. The state legislature meets at the Capitol in Austin. It is a powerful arm of the Texas government not only because of its power of the purse to control and direct the activities of state government and the strong constitutional connections between it and the Lieutenant Governor of Texas, but also due to Texas's plural executive.
```

## 181. `ares_nq_example_2615988099636476869`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who comes after the president if he dies

Answer:

> Rocky

Contexts:

- Context `ares_doc_2615988099636476869`:

```text
The United States presidential line of succession is the order in which officials of the United States federal government assume the powers and duties of the office of President of the United States if the incumbent president becomes incapacitated, dies, resigns, or is removed from office (via impeachment by the House of Representatives and subsequent conviction in a trial by the Senate). Presidential succession is referred to multiple times in the U.S. Constitution, as well as the 12th Amendment, 20th Amendment, and 25th Amendment. The Article II succession clause authorizes Congress to provide for a line of succession beyond the vice president, which it has done on three occasions. The current Presidential Succession Act was adopted in 1947, and last revised in 2006.
```

## 182. `ares_nq_example_6243386362552941358_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> where do the secretory cells of endocrine glands secrete their products

Answer:

> March 2003

Contexts:

- Context `ares_doc_6243386362552941358_2`:

```text
Exocrine glands are glands that produce and secrete substances onto an epithelial surface by way of a duct. Examples of exocrine glands include sweat, salivary, mammary, ceruminous, lacrimal, sebaceous, and mucous. Exocrine glands are one of two types of glands in the human body, the other being endocrine glands, which secrete their products directly into the bloodstream. The liver and pancreas are both exocrine and endocrine glands; they are exocrine glands because they secrete products—bile and pancreatic juice—into the gastrointestinal tract through a series of ducts, and endocrine because they secrete other substances directly into the bloodstream.
```

## 183. `ares_nq_example_2595383962592690378_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> what's the dwarf's name in game of thrones

Answer:

> Tyrion Lannister

Contexts:

- Context `ares_doc_2595383962592690378_2`:

```text
Section::::Main characters.:Tyrion Lannister.
```

## 184. `ares_nq_example_2529995246626301289_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> which philosopher advocated the idea of return to nature

Answer:

> Bacon

Contexts:

- Context `ares_doc_2529995246626301289_2`:

```text
In contrast, Modern Science took its distinctive turn with Francis Bacon, who rejected the four distinct causes, and saw Aristotle as someone who "did proceed in such a spirit of difference and contradiction towards all antiquity: undertaking not only to frame new words of science at pleasure, but to confound and extinguish all ancient wisdom". He felt that lesser known Greek philosophers such as Democritus "who did not suppose a mind or reason in the frame of things", have been arrogantly dismissed because of Aristotelianism leading to a situation in his time wherein "the search of the physical causes hath been neglected, and passed in silence".
```

## 185. `ares_nq_example_819495145099806596`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> what is a coherent set of values and beliefs about public policy called

Answer:

> political ideology

Contexts:

- Context `ares_doc_819495145099806596`:

```text
In social studies, a political ideology is a certain ethical set of ideals, principles, doctrines, myths, or symbols of a social movement, institution, class, or large group that explains how society should work, and offers some political and cultural blueprint for a certain social order. Political ideologies are concerned with many different aspects of a society, including (for example): the economy, education, health care, labor law, criminal law, the justice system, the provision of social security and social welfare, trade, the environment, minors, immigration, race, use of the military, patriotism, and established religion.
```

## 186. `ares_nq_example_143358760627476379`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when does closure of the ductus arteriosus occur

Answer:

> birth

Contexts:

- Context `ares_doc_143358760627476379`:

```text
The ductus arteriosus, also called the ductus Botalli, is a blood vessel in the developing fetus connecting the trunk of the pulmonary artery to the proximal descending aorta. It allows most of the blood from the right ventricle to bypass the fetus's fluid-filled non-functioning lungs. Upon closure at birth, it becomes the ligamentum arteriosum.
```

## 187. `ares_nq_example_2419576910417046724_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> what is the longest pier in the uk

Answer:

> Southend Pier

Contexts:

- Context `ares_doc_2419576910417046724_2`:

```text
Southend Pier
```

## 188. `ares_nq_example_506675028665759748`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when did goku first go super saiyan 4

Answer:

> Dragon Ball GT

Contexts:

- Context `ares_doc_506675028665759748`:

```text
As the protagonist, Goku appears in most of the episodes, films, television specials and OVAs of the manga's anime adaptations ("Dragon Ball", "Dragon Ball Z", "Dragon Ball GT", "Dragon Ball Super" and "Dragon Ball Heroes") as well as many of the franchise's video games. Due to the series' international popularity, Goku has become one of the most recognizable and iconic characters in the world. Outside the "Dragon Ball" franchise, Goku has made cameo appearances in Toriyama's self-parody series "Neko Majin Z", has been the subject of other parodies, and has appeared in special events. Most Western audiences were introduced to the adult version of Goku appearing in the "Dragon Ball Z" anime, itself an adaptation of "Dragon Ball" manga volumes 17-42, as opposed to his initial child form, due to the limited success of the first series overseas. Goku's critical reception has been largely positive and he is often considered to be one of the greatest manga and anime characters of all time.
```

## 189. `ares_nq_example_1560261279486353160_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> where do you get a cashiers check from

Answer:

> a bank

Contexts:

- Context `ares_doc_1560261279486353160_2`:

```text
A cashier's check (or cashier's cheque) is a check guaranteed by a bank, drawn on the bank's own funds and signed by a cashier. Cashier's checks are treated as guaranteed funds because the bank, rather than the purchaser, is responsible for paying the amount. They are commonly required for real estate and brokerage transactions.
```

## 190. `ares_nq_example_8520286983945685639_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> where did hope on bold and beautiful go

Answer:

> The Royalettes

Contexts:

- Context `ares_doc_8520286983945685639_2`:

```text
After finding out about Quinn's involvement in Ridge's disappearance and feared death, Hope chooses Liam and they become engaged. Quinn becomes outraged when Hope ends things with Wyatt, and threatens both Liam and Hope's lives. When Quinn tries to kill Liam once and for all, Wyatt and Deacon Sharpe save him. Wyatt declares his support for Liam and Hope's relationship. Because of this, Liam and Hope decide to rehire Wyatt at Forrester Creations. Wyatt inherits the Hope for the Future Diamond after Ricardo Montemayor dies. He gifts it to Hope, which causes friction between Liam and Hope, and the two brothers. When Liam demands Hope give it back to Wyatt, Hope refuses, and publicly declares at a press conference that she is keeping the diamond. Wyatt and Rick decide to take Hope and the diamond on a promotion tour, starting with a photo shoot in Paris. Hope asks Liam to come with her, or meet her there to marry her. But Liam, still angry, does not know if he will go. Hope tells him to meet her at 3pm the next day after the photo shoot if he wants to continue their relationship. Wyatt begs Hope not to marry Liam, though she insists that she and Liam belong together. Liam misses his deadline with Hope, who then leaves with Wyatt on the Spencer jet. Wyatt takes her to Bill's yacht in Monte Carlo, where he insists that Liam wasted all of his chances with Hope, but that he will always be there for her. Wyatt proposes to Hope using the HFTF diamond, and Hope accepts and marries Wyatt. She realizes Wyatt is the man she had wanted the whole time, and that a life with Liam was just a fantasy for her. Although Liam revealed that he was indeed at Paris at the time she left, she remained positive on making her commitment to Wyatt. However, about a month later, Hope gets an urgent call from Liam. She finds out that Quinn orchestrated her and Wyatt's marriage by pushing Ivy off the Seine causing Liam to miss his chance to be with Hope. After confronting Quinn for her role and Wyatt for defending his mother, though she also feel sympathy for him, she was determined to leave Wyatt to be with Liam again until she announced that she is pregnant with Wyatt's child. She explains that she doesn't want her child to grow up with multiple fathers and have a complicated relationship like she did. She ended things with Liam for good and wants to rekindle her marriage to Wyatt now with the baby on the way. This is all changed when she suffers a miscarriage, and tells Liam that she will always love him. Hope visits Brooke in Milan, Italy, and does not return to L.A. with Brooke.
```

## 191. `ares_nq_example_4373262132142058334_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> mention the chemical change that proinsulin undergo to be able to act as mature insulin

Answer:

> post translational modification

Contexts:

- Context `ares_doc_4373262132142058334_2`:

```text
The post translational modification of proinsulin to mature insulin only occurs in the beta cells of the islets of Langerhans. When proinsulin is transported through the Golgi apparatus the C-peptide is cleaved. This cleavage occurs with the aid of two endoproteases. Type I endoproteases, PC1 and PC3, disrupt the C peptide-B chain connection. PC2, a type II endoprotease, cleaves the C peptide-A chain bond. The resulting molecule, now mature insulin, is stored as a hexamer in secretory vesicles and is stabilized with formula_1 molecules until it is secreted.
```

## 192. `ares_nq_example_6345284186404798651_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> when did world war one begin and end

Answer:

> mid-March

Contexts:

- Context `ares_doc_6345284186404798651_2`:

```text
World War I (often abbreviated as WWI or WW1), also known as the First World War or the Great War, was a global war originating in Europe that lasted from 28 July 1914 to 11 November 1918. Contemporaneously described as, "the war to end all wars," it led to the mobilisation of more than 70 million military personnel, including 60 million Europeans, making it one of the largest wars in history. It is also one of the deadliest conflicts in history, with an estimated nine million combatants and seven million civilian deaths as a direct result of the war, while resulting genocides and the resulting 1918 influenza pandemic caused another 50 to 100 million deaths worldwide.
```

## 193. `ares_nq_example_3339006116507262453_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> who sang i ran all the way home

Answer:

> Parashara

Contexts:

- Context `ares_doc_3339006116507262453_2`:

```text
The Impalas
```

## 194. `ares_nq_example_8803717720023296980`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> where does the sciatic nerve run in the foot

Answer:

> on the posterior aspect

Contexts:

- Context `ares_doc_8803717720023296980`:

```text
The sciatic nerve (also called "ischiadic nerve", "ischiatic nerve") is a large nerve in humans and other animals. It begins in the lower back and runs through the buttock and down the lower limb. It is the longest and widest single nerve in the human body, going from the top of the leg to the foot on the posterior aspect. The sciatic nerve provides the connection to the nervous system for nearly the whole of the skin of the leg, the muscles of the back of the thigh, and those of the leg and foot. It is derived from spinal nerves L4 to S3. It contains fibers from both the anterior and posterior divisions of the lumbosacral plexus.
```

## 195. `ares_nq_example_3530165048900528552_2`

- Source: `ARES/NQ example`
- Expected labels: `should_have_abstained, unsupported_answer`
- Expected root cause: `should_have_abstained`

Query:

> which foreign currency option is the​ right but not the​ obligation to buy foreign​ currency

Answer:

> Liam Cunningham

Contexts:

- Context `ares_doc_3530165048900528552_2`:

```text
In finance, a foreign exchange option (commonly shortened to just FX option or currency option) is a derivative financial instrument that gives the right but not the obligation to exchange money denominated in one currency into another currency at a pre-agreed exchange rate on a specified date. See Foreign exchange derivative.
```

## 196. `ares_nq_example_7184968347544956967`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who plays genie in ferris bueller's day off

Answer:

> Jennifer Grey

Contexts:

- Context `ares_doc_7184968347544956967`:

```text
In suburban Chicago, Illinois, near the end of the school year, high school senior Ferris Bueller (Matthew Broderick) fakes being sick to stay home. Throughout the film, Ferris frequently breaks the fourth wall to talk about his friends and give the audience advice on how to skip school. His parents believe him, though his sister Jeanie (Jennifer Grey) is not convinced. Dean of Students Edward R. Rooney (Jeffrey Jones) suspects Ferris is being truant again and commits to catching him. Ferris convinces his best friend Cameron Frye (Alan Ruck), who is legitimately absent due to illness, to help lure Ferris' girlfriend Sloane Peterson (Mia Sara) out of school by reporting that her grandmother has died. To trick Rooney, Ferris sways Cameron to let them use his father's prized 1961 Ferrari 250 GT California Spyder to collect Sloane. Cameron is dismayed when Ferris continues to use the car to drive them into downtown Chicago to spend the day, but Ferris promises they will return it as it was.
```

## 197. `ares_nq_example_530230237658072225_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> who formed the indian society of oriental art

Answer:

> Abanindranath Tagore

Contexts:

- Context `ares_doc_530230237658072225_2`:

```text
Abanindranath Tagore
```

## 198. `ares_nq_example_6482049414864375394_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> when did korn's follow the leader come out

Answer:

> August 18 , 1998

Contexts:

- Context `ares_doc_6482049414864375394_2`:

```text
"Follow the Leader" is recognized as Korn's mainstream breakthrough, and the album that launched nu metal into the mainstream. "Follow the Leader" was released August 18, 1998, and was awarded multi-platinum certification for shipments in excess of five million copies, by the RIAA on March 15, 2002. In fall of 1998, Korn started the Family Values Tour. According to Arvizu, the tour name was due to "so many of their friends who were like family to us played in bands". The tour started on September 22, 1998, ending on October 31, 1998. The tour grossed over 6.4 million (6,400,000). Korn maintained a generally low ticket price, usually no more than thirty dollars. Korn toured with the band Limp Bizkit, as well as Ice Cube, Orgy, Incubus, and Rammstein. The tour was considered to be a major success, and promoted "Follow the Leader" to sales that were considered to have "skyrocketed". However, unlike all their other tours, they opted not to play in Europe for this cycle.
```

## 199. `ares_nq_example_7569792100939124605`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> where is the light between two oceans filmed

Answer:

> New Zealand

Contexts:

- Context `ares_doc_7569792100939124605`:

```text
The Light Between Oceans is a 2016 romantic drama written and directed by Derek Cianfrance and based on the 2012 novel "The Light Between Oceans" by M. L. Stedman. An international co-production between the United States, Australia, the United Kingdom, and New Zealand, the film stars Michael Fassbender, Alicia Vikander, Rachel Weisz, Bryan Brown, and Jack Thompson. The film tells the story of a lighthouse keeper and his wife who rescue and adopt an infant girl adrift at sea. Years later, the couple discover the child's true parentage and are faced with the moral dilemma of their actions.
```

## 200. `ares_nq_example_333763277804609492_2`

- Source: `ARES/NQ example`
- Expected labels: `no_failure_detected`
- Expected root cause: `no_failure_detected`

Query:

> a player that can shoot pass or dribble is considered to be

Answer:

> Triple threat

Contexts:

- Context `ares_doc_333763277804609492_2`:

```text
Section::::Triple threat position and related moves.
```
