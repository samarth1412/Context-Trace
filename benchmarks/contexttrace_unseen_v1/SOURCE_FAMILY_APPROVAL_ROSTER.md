# ContextTrace-Unseen-v1 source-family approval roster

Roster version: 0.1

Prepared: 2026-07-24

Status: proposed for user and license-review approval; acquisition prohibited

## Purpose

This is the proposed minimum 36-family pool for the Natural OOD track. It is a
family-level planning record, not a populated source manifest and not proof
that any particular document is eligible.

No page, repository, archive, or API response may be downloaded for corpus use
until:

1. the project owner approves this roster;
2. the license/privacy reviewer confirms the exact document path, license,
   attribution, access method, and hosted-model transmission permission; and
3. the calibration registry shows no source-family, fine-domain, document,
   publication-window, hash, or near-duplicate overlap.

The proposed sources are English-language official materials. Repository
licenses apply only after the reviewer confirms that the selected documentation
path is covered by the stated repository license.

## Calibration exclusions already identified

An automated repository scan found prior inspection of these families or
publishers, so they are excluded even if a new page could be found:

`Arize/Phoenix`, `AWS`, `Chroma`, `DeepEval`, `Django`, `Docker`, `DSPy`,
`Elastic`, `FastAPI`, `GitHub Actions`, `Google Cloud`, `Guardrails`,
`Haystack`, `Kubernetes`, `LanceDB`, `LangChain`, `LlamaIndex`, `Microsoft
Azure`, `Milvus`, `MongoDB`, `OpenAI`, `OpenSearch`, `OpenTelemetry`,
`Pinecone`, `PostgreSQL`, `Pydantic`, `Python`, `Qdrant`, `RAGAS`, `Redis`,
`SQLAlchemy`, `TruLens`, `Vespa`, and `Weaviate`.

This is a lower bound on calibration exposure, not the finished calibration
registry. Family aliases and sources inspected outside the repository still
require human disclosure.

## A. Software and product documentation

| ID | Proposed source family | Fine-grained domain | Official source | License basis to verify |
| --- | --- | --- | --- | --- |
| `sw_gitlab` | GitLab documentation | DevOps platform | <https://docs.gitlab.com/> | Documentation content stated as CC BY-SA 4.0: <https://docs.gitlab.com/legal/developer_certificate_of_origin/> |
| `sw_rust` | Rust documentation | systems language | <https://github.com/rust-lang/rust/tree/master/src/doc> | MIT OR Apache-2.0 repository terms: <https://github.com/rust-lang/rust#license> |
| `sw_go` | Go documentation | systems language/toolchain | <https://github.com/golang/go/tree/master/doc> | BSD-3-Clause: <https://github.com/golang/go/blob/master/LICENSE> |
| `sw_nodejs` | Node.js documentation | server runtime | <https://github.com/nodejs/node/tree/main/doc> | Repository license notices: <https://github.com/nodejs/node/blob/main/LICENSE> |
| `sw_ruby` | Ruby documentation | programming language | <https://github.com/ruby/ruby/tree/master/doc> | Ruby/BSD-style terms: <https://github.com/ruby/ruby/blob/master/COPYING> |
| `sw_spark` | Apache Spark documentation | distributed data processing | <https://github.com/apache/spark/tree/master/docs> | Apache-2.0: <https://github.com/apache/spark/blob/master/LICENSE> |
| `sw_flink` | Apache Flink documentation | stream processing | <https://github.com/apache/flink/tree/master/docs> | Apache-2.0: <https://github.com/apache/flink/blob/master/LICENSE> |
| `sw_beam` | Apache Beam documentation | data-processing SDK | <https://github.com/apache/beam/tree/master/website> | Apache-2.0: <https://github.com/apache/beam/blob/master/LICENSE> |
| `sw_airflow` | Apache Airflow documentation | workflow orchestration | <https://github.com/apache/airflow/tree/main/docs> | Apache-2.0: <https://github.com/apache/airflow/blob/main/LICENSE> |
| `sw_numpy` | NumPy documentation | numerical computing | <https://github.com/numpy/numpy/tree/main/doc> | BSD-3-Clause-style terms: <https://github.com/numpy/numpy/blob/main/LICENSE.txt> |
| `sw_pandas` | pandas documentation | tabular data analysis | <https://github.com/pandas-dev/pandas/tree/main/doc> | BSD-3-Clause: <https://github.com/pandas-dev/pandas/blob/main/LICENSE> |
| `sw_jupyterlab` | JupyterLab documentation | interactive computing UI | <https://github.com/jupyterlab/jupyterlab/tree/main/docs> | BSD-3-Clause: <https://github.com/jupyterlab/jupyterlab/blob/main/LICENSE> |

Software-family documents will be chosen from released tags, not an unversioned
default branch. A release tag and commit SHA are both recorded. GitLab pages
require an equivalent immutable archive or repository commit.

## B. Policy and regulatory documents

The policy stratum uses official regulatory text from eCFR/GovInfo rather than
third-party summaries. A source family is the issuing agency and regulatory
program, not the common publishing host.

| ID | Proposed source family | Fine-grained domain | Official collection |
| --- | --- | --- | --- |
| `reg_sec` | SEC securities regulation | securities markets | 17 CFR: <https://www.ecfr.gov/current/title-17> |
| `reg_ftc` | FTC commercial-practices regulation | consumer/commercial practices | 16 CFR: <https://www.ecfr.gov/current/title-16> |
| `reg_fda` | FDA food and drug regulation | food/drug safety | 21 CFR: <https://www.ecfr.gov/current/title-21> |
| `reg_cfpb` | CFPB consumer-finance regulation | consumer finance | 12 CFR, Chapter X: <https://www.ecfr.gov/current/title-12/chapter-X> |
| `reg_osha` | OSHA workplace-safety regulation | occupational safety | 29 CFR, Subtitle B: <https://www.ecfr.gov/current/title-29/subtitle-B> |
| `reg_epa` | EPA environmental regulation | environmental protection | 40 CFR: <https://www.ecfr.gov/current/title-40> |
| `reg_fcc` | FCC telecommunications regulation | communications | 47 CFR: <https://www.ecfr.gov/current/title-47> |
| `reg_cms` | CMS health-program regulation | public health programs | 42 CFR, Chapter IV: <https://www.ecfr.gov/current/title-42/chapter-IV> |
| `reg_faa` | FAA aviation regulation | civil aviation | 14 CFR: <https://www.ecfr.gov/current/title-14> |
| `reg_nrc` | NRC nuclear-safety regulation | nuclear safety | 10 CFR, Chapter I: <https://www.ecfr.gov/current/title-10/chapter-I> |
| `reg_usda` | USDA agricultural regulation | agriculture | 7 CFR: <https://www.ecfr.gov/current/title-7> |
| `reg_dot` | DOT transportation regulation | transportation | 49 CFR: <https://www.ecfr.gov/current/title-49> |

License/access basis to review for every selected unit:

- GovInfo states that U.S. Government works are generally public domain under
  17 U.S.C. 105 while warning that a government publication may contain
  third-party copyrighted material:
  <https://www.govinfo.gov/about/policies>.
- eCFR is the continuously updated official online version of the CFR:
  <https://www.ecfr.gov/>.

Eligibility is limited to the official regulatory text and government-authored
metadata. Editorial annotations, incorporated standards, images, forms,
third-party material, and copyrighted material incorporated by reference are
excluded unless separately licensed. The reviewer must record the issuing
agency, CFR hierarchy, effective/amendment dates, and any incorporation by
reference.

The production snapshot will use official XML/text where available. A rendered
web page is not treated as the legal source when the page warns otherwise.

## C. Support and operational knowledge

This group deliberately uses official operator, administration, deployment,
upgrade, and troubleshooting documentation from twelve Apache projects. They
share a license steward but remain separate product/source families and
fine-grained operational domains.

| ID | Proposed source family | Fine-grained domain | Official documentation source |
| --- | --- | --- | --- |
| `ops_kafka` | Apache Kafka operations | event streaming | <https://github.com/apache/kafka/tree/trunk/docs> |
| `ops_cassandra` | Apache Cassandra operations | distributed database | <https://github.com/apache/cassandra/tree/trunk/doc> |
| `ops_hadoop` | Apache Hadoop operations | distributed storage/compute | <https://github.com/apache/hadoop/tree/trunk/hadoop-project> |
| `ops_hbase` | Apache HBase operations | distributed wide-column database | <https://github.com/apache/hbase/tree/master/hbase-website> |
| `ops_zookeeper` | Apache ZooKeeper administration | coordination service | <https://github.com/apache/zookeeper/tree/master/zookeeper-website> |
| `ops_pulsar` | Apache Pulsar administration | messaging/streaming | <https://github.com/apache/pulsar-site/tree/main/docs> |
| `ops_solr` | Apache Solr operations | search platform | <https://github.com/apache/solr/tree/main/solr/solr-ref-guide> |
| `ops_druid` | Apache Druid operations | analytics datastore | <https://github.com/apache/druid/tree/master/docs> |
| `ops_tomcat` | Apache Tomcat administration | application server | <https://github.com/apache/tomcat/tree/main/webapps/docs> |
| `ops_httpd` | Apache HTTP Server operations | web server | <https://github.com/apache/httpd/tree/trunk/docs> |
| `ops_artemis` | Apache ActiveMQ Artemis operations | message broker | <https://github.com/apache/activemq-artemis/tree/main/docs> |
| `ops_camel` | Apache Camel operations | integration runtime | <https://github.com/apache/camel/tree/main/docs> |

The proposed license basis is Apache-2.0, confirmed at the selected tagged
repository revision and against <https://www.apache.org/licenses/LICENSE-2.0>.
The reviewer must also preserve repository `NOTICE` content and generated-page
attribution where required.

## Diversity and allocation constraints

- The initial Natural OOD target is 396 cases: 132 per domain group and 11 per
  source family.
- The acceptable production range remains 300–500; no family may exceed 10%.
- Every domain group receives BM25, dense-vector, and hybrid retrieval.
- Generator, chunk-size, overlap, and reranking allocations are balanced
  independently of source content and labels.
- A family that fails license, overlap, privacy, availability, or snapshot
  review is replaced before schedule freeze; its cases are not silently moved
  to another retained family.
- Temporal/source-condition cases use distinct source documents and their own
  prespecified pair allocation.

The count is a planning target. It is not evidence that clean and naturally
failing answer classes will be balanced; answers are retained under mechanical
eligibility rules without label inspection.

## Approval choices

The project owner should choose one:

- **7A — Approve the proposed roster for document-level review.** This
  authorizes license/overlap review and preparation of exact document
  candidates, but not downloading corpus content until those reviews pass.
- **7B — Approve except named replacements.** Supply the family IDs to replace
  and, optionally, preferred alternatives.
- **7C — Do not approve.** Redesign one or more domain groups before continuing.

Even with 7A, any family discovered in calibration exposure is automatically
removed and returned for replacement approval.
