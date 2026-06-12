import json

import pytest

from contexttrace.cli import main
from contexttrace.verify import verify_trace
from contexttrace.verify.benchmark import run_verify_benchmark
from contexttrace.verify.claims import extract_claims
from contexttrace.verify.evidence import find_best_evidence
from contexttrace.verify.facts import compare_facts, extract_required_facts
from contexttrace.verify.judges import JudgeVerdict
from contexttrace.verify.report import VerifyReportGenerator
from contexttrace.verify.schema import (
    RAGTrace,
    TraceCitation,
    TraceContext,
    VerificationInputError,
    load_trace,
    load_trace_file,
)
from contexttrace.verify.spans import split_context_spans


class StaticJudge:
    def __init__(self, verdicts):
        self.verdicts = list(verdicts)
        self.calls = []

    def verify_claim(self, *, query, claim, contexts):
        self.calls.append(
            {
                "query": query,
                "claim": claim,
                "context_ids": [context.id for context in contexts],
                "context_texts": [context.text for context in contexts],
                "context_metadata": [dict(context.metadata) for context in contexts],
            }
        )
        if len(self.verdicts) == 1:
            return self.verdicts[0]
        return self.verdicts.pop(0)


def test_verify_schema_loads_valid_trace(tmp_path):
    path = tmp_path / "trace.json"
    path.write_text(
        json.dumps(
            {
                "query": "What is the refund policy?",
                "answer": "Refunds are allowed within 30 days.",
                "contexts": [
                    {
                        "id": "policy_2026",
                        "text": "Customers may request refunds within 30 days.",
                        "metadata": {"source": "refund_policy.pdf"},
                    }
                ],
                "citations": [
                    {
                        "claim": "Refunds are allowed within 30 days.",
                        "source_id": "policy_2026",
                    }
                ],
                "metadata": {"run_id": "demo"},
            }
        ),
        encoding="utf-8",
    )

    trace = load_trace_file(path)

    assert trace.query == "What is the refund policy?"
    assert trace.contexts[0].id == "policy_2026"
    assert trace.citations[0].source_id == "policy_2026"
    assert trace.metadata["run_id"] == "demo"


def test_verify_schema_rejects_invalid_trace():
    with pytest.raises(VerificationInputError, match="contexts"):
        load_trace({"query": "Q", "answer": "A"})

    with pytest.raises(VerificationInputError, match="contexts\\[0\\].*text"):
        load_trace({"query": "Q", "answer": "A", "contexts": [{"id": "ctx"}]})


def test_verify_cli_reports_invalid_json(tmp_path, capsys):
    path = tmp_path / "bad.json"
    path.write_text("{not-json", encoding="utf-8")

    assert main(["verify", str(path)]) == 1

    assert "Invalid JSON" in capsys.readouterr().err


def test_claim_extraction_splits_sentences_and_skips_filler():
    claims = extract_claims(
        "Sure. Refunds are allowed within 30 days. Refunds are processed in 5 business days."
    )

    assert [claim.id for claim in claims] == ["claim_1", "claim_2"]
    assert [claim.text for claim in claims] == [
        "Refunds are allowed within 30 days.",
        "Refunds are processed in 5 business days.",
    ]


def test_claim_extraction_decomposes_simple_compound_claims():
    claims = extract_claims(
        "Refunds are allowed within 30 days and processed within 5 business days."
    )

    assert [claim.text for claim in claims] == [
        "Refunds are allowed within 30 days.",
        "Refunds are processed within 5 business days.",
    ]


def test_claim_extraction_does_not_split_noun_lists():
    claims = extract_claims("Customers can request refunds and exchanges within 30 days.")

    assert [claim.text for claim in claims] == [
        "Customers can request refunds and exchanges within 30 days."
    ]


def test_claim_extraction_preserves_full_subject_for_main_verb_compounds():
    claims = extract_claims(
        "A Haystack Document Store stores documents and is commonly used to fetch documents with a Retriever."
    )

    assert [claim.text for claim in claims] == [
        "A Haystack Document Store stores documents.",
        "A Haystack Document Store is commonly used to fetch documents with a Retriever.",
    ]


def test_claim_extraction_preserves_versions_and_paths():
    claims = extract_claims(
        "ContextTrace v0.2.0 stores traces under .contexttrace/contexttrace.db."
    )

    assert [claim.text for claim in claims] == [
        "ContextTrace v0.2.0 stores traces under .contexttrace/contexttrace.db."
    ]


def test_claim_extraction_preserves_jsonpath_expressions():
    claims = extract_claims(
        "Endpoint response mapping supports $.answer, $.contexts, $.citations, dotted fields, and numeric indexes."
    )

    assert [claim.text for claim in claims] == [
        "Endpoint response mapping supports $.answer, $.contexts, $.citations, dotted fields, and numeric indexes."
    ]


def test_context_span_extraction_preserves_offsets_and_hashes():
    context = TraceContext(
        id="docs/local-mode.md",
        text="ContextTrace v0.2.0 is local-first. It stores traces under .contexttrace/contexttrace.db.",
    )

    spans = split_context_spans(context)

    assert [span.text for span in spans] == [
        "ContextTrace v0.2.0 is local-first.",
        "It stores traces under .contexttrace/contexttrace.db.",
    ]
    assert spans[0].start_char == 0
    assert context.text[spans[1].start_char : spans[1].end_char] == spans[1].text
    assert spans[0].span_hash.startswith("sha256:")


def test_fact_extraction_and_matching_identifies_missing_detail():
    claim = (
        "The LangChain callback captures query, retrieved documents, selected context, "
        "and logging failures are swallowed by default."
    )
    evidence = (
        "It captures query/input, retrieved documents, selected context, final answer/output, "
        "citations when the chain returns them, metadata, tags, run IDs, model, token usage, "
        "and latency."
    )

    assert extract_required_facts(claim) == [
        "captures query",
        "retrieved documents",
        "selected context",
        "logging failures are swallowed by default",
    ]

    match = compare_facts(claim, evidence, mode="semantic")

    assert match.matched_facts == [
        "captures query",
        "retrieved documents",
        "selected context",
    ]
    assert match.missing_facts == ["logging failures are swallowed by default"]


def test_fact_matching_supports_list_items_with_equivalent_list_header():
    match = compare_facts(
        "Supported event types include planner_step, tool_call, and tool_result.",
        "Supported event types are planner_step, tool_call, and tool_result.",
        mode="semantic",
    )

    assert match.missing_facts == []
    assert match.matched_facts == ["include planner_step", "include tool_call", "include tool_result"]
    assert match.matched_fact_details[0].type == "predicate"


def test_evidence_matching_finds_best_context_and_terms():
    contexts = [
        TraceContext(id="shipping", text="Standard shipping takes 3 to 5 business days."),
        TraceContext(id="policy", text="Customers may request refunds within 30 days of purchase."),
    ]

    match = find_best_evidence("Refunds are allowed within 30 days.", contexts)

    assert match.context_id == "policy"
    assert match.score >= 0.6
    assert "refunds" in match.matched_terms
    assert "30" in match.matched_terms


def test_supported_claim_classification():
    result = verify_trace(
        RAGTrace(
            query="What is the refund policy?",
            answer="Refunds are allowed within 30 days.",
            contexts=[
                TraceContext(
                    id="policy",
                    text="Customers may request refunds within 30 days of purchase.",
                )
            ],
            citations=[
                TraceCitation(
                    claim="Refunds are allowed within 30 days.",
                    source_id="policy",
                )
            ],
        )
    )

    assert result["summary"]["supported"] == 1
    assert result["summary"]["support_rate"] == 1.0
    assert result["summary"]["unsupported_claim_rate"] == 0.0
    assert result["summary"]["failure_type"] == "no_failure_detected"
    assert result["summary"]["primary_root_cause"] == "no_failure_detected"
    assert result["claims"][0]["verdict"] == "supported"
    assert result["claims"][0]["support_status"] == "grounded_by_span"
    assert result["claims"][0]["truth_status"] == "not_assessed"
    assert result["claims"][0]["source_status"] == "freshness_unknown"
    assert "independently true" in result["claims"][0]["status_note"]
    assert result["claims"][0]["citation_status"] == "citation_ok"
    assert result["claims"][0]["root_cause"]["label"] == "no_failure_detected"


def test_source_status_is_separate_from_grounding():
    result = verify_trace(
        RAGTrace(
            query="What is the refund policy?",
            answer="Refunds are allowed within 30 days.",
            contexts=[
                TraceContext(
                    id="policy",
                    text="Customers may request refunds within 30 days of purchase.",
                    metadata={"source_status": "stale_source"},
                )
            ],
        )
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["support_status"] == "grounded_by_span"
    assert claim["truth_status"] == "not_assessed"
    assert claim["source_status"] == "grounded_but_stale"
    assert claim["root_cause"]["label"] == "stale_context"
    assert result["summary"]["source_status"] == "grounded_but_stale"
    assert result["summary"]["failure_type"] == "stale_source"


def test_supported_claim_with_stronger_conflicting_source_is_flagged():
    result = verify_trace(
        RAGTrace(
            query="What is the refund window?",
            answer="Refunds are available within 30 days.",
            contexts=[
                TraceContext(
                    id="policy_old",
                    text="Refunds are available within 30 days.",
                    metadata={
                        "source_group": "refund_policy",
                        "source_version": "2024.1",
                        "source_authority": "medium",
                    },
                ),
                TraceContext(
                    id="policy_current",
                    text="Refunds are available within 14 days.",
                    metadata={
                        "source_group": "refund_policy",
                        "source_version": "2026.1",
                        "canonical": True,
                        "source_authority": "official",
                    },
                ),
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["source_status"] == "grounded_but_stale"
    assert claim["root_cause"]["label"] == "stale_context"
    assert "stale_source" in result["summary"]["failure_types"]
    assert claim["source_assessment"]["newer_related_sources"][0]["context_id"] == "policy_current"


def test_canonical_supported_source_wins_over_lower_authority_conflict():
    result = verify_trace(
        RAGTrace(
            query="What is the refund window?",
            answer="Refunds are available within 14 days.",
            contexts=[
                TraceContext(
                    id="policy_current",
                    text="Refunds are available within 14 days.",
                    metadata={
                        "source_group": "refund_policy",
                        "source_version": "2026.1",
                        "canonical": True,
                        "source_authority": "official",
                    },
                ),
                TraceContext(
                    id="policy_old",
                    text="Refunds are available within 30 days.",
                    metadata={
                        "source_group": "refund_policy",
                        "source_version": "2024.1",
                        "source_authority": "low",
                    },
                ),
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["source_status"] == "supported_by_canonical_source"
    assert claim["root_cause"]["label"] == "no_failure_detected"
    assert result["summary"]["failure_type"] == "no_failure_detected"
    assert claim["source_assessment"]["conflicting_sources"][0]["context_id"] == "policy_old"


def test_low_authority_supported_source_is_flagged():
    result = verify_trace(
        RAGTrace(
            query="What is the refund window?",
            answer="Refunds are available within 30 days.",
            contexts=[
                TraceContext(
                    id="community_post",
                    text="Refunds are available within 30 days.",
                    metadata={
                        "source_authority": "low",
                        "source": "community/forum-post.md",
                    },
                )
            ],
        )
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["source_status"] == "grounded_by_low_authority_source"
    assert claim["root_cause"]["label"] == "low_authority_source"
    assert result["summary"]["failure_type"] == "low_authority_source"
    assert claim["source_assessment"]["best_source"]["authority_score"] == 0.25


def test_unsupported_claim_classification():
    result = verify_trace(
        RAGTrace(
            query="How long does refund processing take?",
            answer="Refunds are processed within 5 business days.",
            contexts=[
                TraceContext(
                    id="policy",
                    text="Customers may request refunds within 30 days of purchase.",
                )
            ],
        )
    )

    assert result["summary"]["unsupported"] == 1
    assert result["summary"]["unsupported_claim_rate"] == 1.0
    assert "unsupported_answer" in result["summary"]["failure_types"]
    assert result["claims"][0]["verdict"] == "unsupported"
    assert result["claims"][0]["root_cause"]["missing_fact"]


def test_partially_supported_claim_classification():
    result = verify_trace(
        RAGTrace(
            query="Can customers request refunds within 30 days?",
            answer="Refunds within 30 days require manager approval.",
            contexts=[
                TraceContext(
                    id="policy",
                    text="Customers may request refunds within 30 days of purchase.",
                )
            ],
        )
    )

    assert result["summary"]["partially_supported"] == 1
    assert result["summary"]["support_rate"] == 0.0
    assert "partial_support" in result["summary"]["failure_types"]
    assert result["summary"]["failure_type"] == "partial_support"
    assert result["abstention"]["should_abstain"] is False
    assert result["claims"][0]["verdict"] == "partially_supported"
    assert "missing_facts" in result["claims"][0]
    assert "evidence_span" in result["claims"][0]
    assert result["claims"][0]["root_cause"]["label"] == "answer_overreach"
    assert result["summary"]["root_causes"]["answer_overreach"] == 1


def test_partial_support_includes_matched_and_missing_facts():
    result = verify_trace(
        RAGTrace(
            query="What does the LangChain callback capture?",
            answer=(
                "The LangChain callback captures query, retrieved documents, selected context, "
                "and logging failures are swallowed by default."
            ),
            contexts=[
                TraceContext(
                    id="langchain_docs",
                    text=(
                        "It captures query/input, retrieved documents, selected context, final answer/output, "
                        "citations when the chain returns them, metadata, tags, run IDs, model, token usage, "
                        "and latency."
                    ),
                )
            ],
        )
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "partially_supported"
    assert claim["matched_facts"] == [
        "captures query",
        "retrieved documents",
        "selected context",
    ]
    assert claim["missing_facts"] == ["logging failures are swallowed by default"]
    assert claim["evidence_span"]["span_hash"].startswith("sha256:")
    assert claim["missing_fact_details"][0]["type"] == "predicate"


def test_partial_answer_can_include_unverifiable_detail():
    result = verify_trace(
        RAGTrace(
            query="What does Pinecone metadata filtering do?",
            answer=(
                "A Pinecone metadata filter limits search to matching records. "
                "It re-embeds every record during search."
            ),
            contexts=[
                TraceContext(
                    id="pinecone_metadata_filter",
                    text=(
                        "When you search the Pinecone index, you can include a metadata filter "
                        "to limit the search to records matching the filter expression."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    assert [claim["verdict"] for claim in result["claims"]] == ["supported", "unverifiable"]
    assert result["abstention"]["partial_answer"] is True
    assert result["abstention"]["should_abstain"] is False
    assert result["summary"]["failure_types"] == ["partial_support"]
    assert result["claims"][1]["root_cause"]["label"] == "answer_overreach"


def test_conditional_without_does_not_create_negation_conflict():
    result = verify_trace(
        RAGTrace(
            query="What happens when Pinecone search has no metadata filter?",
            answer="A Pinecone search without metadata filters searches the entire namespace.",
            contexts=[
                TraceContext(
                    id="pinecone_indexing_overview",
                    text=(
                        "When querying a Pinecone index, searches without metadata filters "
                        "do not consider metadata and search the entire namespace."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    assert result["claims"][0]["verdict"] == "supported"
    assert result["claims"][0]["conflicting_facts"] == []
    assert result["summary"]["failure_type"] == "no_failure_detected"


def test_strong_negation_conflicts_with_affirmative_evidence():
    result = verify_trace(
        RAGTrace(
            query="Does Chroma recompute embeddings when update documents omit embeddings?",
            answer="Chroma never recomputes embeddings when documents are supplied without embeddings.",
            contexts=[
                TraceContext(
                    id="chroma_update_data",
                    text=(
                        "If documents are supplied without corresponding embeddings, "
                        "the embeddings will be recomputed with the collection's embedding function."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    assert result["claims"][0]["verdict"] == "contradicted"
    assert result["claims"][0]["root_cause"]["label"] == "conflicting_contexts"
    assert "contradicted_answer" in result["summary"]["failure_types"]


def test_semantic_mode_supports_paraphrased_evidence():
    trace = RAGTrace(
        query="What is the refund policy?",
        answer="Refunds are allowed within 30 days.",
        contexts=[
            TraceContext(
                id="policy",
                text="Customers can request money back within thirty days of purchase.",
            )
        ],
    )

    lexical = verify_trace(trace)
    semantic = verify_trace(trace, mode="semantic")

    assert lexical["claims"][0]["verdict"] != "supported"
    assert semantic["claims"][0]["verdict"] == "supported"
    assert semantic["summary"]["mode"] == "semantic"


def test_semantic_mode_supports_prompt_receiving_paraphrase():
    result = verify_trace(
        RAGTrace(
            query="What does a Haystack generator output?",
            answer="Haystack generators generate text after receiving a prompt.",
            contexts=[
                TraceContext(
                    id="haystack_generators",
                    text="Generators are responsible for generating text after you give them a prompt.",
                )
            ],
            citations=[
                TraceCitation(
                    claim="Haystack generators generate text after receiving a prompt.",
                    source_id="haystack_generators",
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["citation_status"] == "citation_ok"
    assert result["summary"]["failure_types"] == ["no_failure_detected"]


def test_semantic_mode_does_not_treat_not_only_as_contradiction():
    result = verify_trace(
        RAGTrace(
            query="What constrains defamation law?",
            answer="Defamation law is balanced against First Amendment and Virginia Constitution speech protections.",
            contexts=[
                TraceContext(
                    id="defamation",
                    text=(
                        "Of course, the law of defamation must be balanced against the freedom of speech "
                        "protected under not only the First Amendment to the United States Constitution, "
                        "but also the Virginia Constitution."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    assert result["claims"][0]["verdict"] == "supported"
    assert result["claims"][0]["conflicting_facts"] == []
    assert "contradicted_answer" not in result["summary"]["failure_types"]


def test_semantic_mode_ignores_negated_aside_when_affirmative_clause_supports_claim():
    result = verify_trace(
        RAGTrace(
            query="Were the Hawks players arrested?",
            answer="Pero Antic and Thabo Sefolosha were arrested on obstruction and disorderly conduct charges.",
            contexts=[
                TraceContext(
                    id="nba_arrests",
                    text=(
                        "A knife was recovered, a suspect was arrested and two individuals not involved "
                        "in the dispute -- the Hawks' Pero Antic, 32, and Thabo Sefolosha, 30 -- were "
                        "arrested on charges of obstructing governmental administration and disorderly conduct."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    assert result["claims"][0]["verdict"] != "contradicted"
    assert result["claims"][0]["conflicting_facts"] == []
    assert "contradicted_answer" not in result["summary"]["failure_types"]


def test_semantic_mode_supports_news_paraphrases():
    discharged = verify_trace(
        RAGTrace(
            query="What happened after King's hospitalization?",
            answer="King has been discharged from the hospital.",
            contexts=[
                TraceContext(
                    id="bb_king",
                    text='"I\'m feeling much better and am leaving the hospital today," King said.',
                )
            ],
        ),
        mode="semantic",
    )
    plant = verify_trace(
        RAGTrace(
            query="Why did the Broken Arrow site close?",
            answer="The Broken Arrow plant is shutting down to investigate contamination.",
            contexts=[
                TraceContext(
                    id="blue_bell",
                    text=(
                        'The company is shutting down the Broken Arrow facility "out of an abundance '
                        'of caution" to search for a possible cause of contamination.'
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    assert discharged["claims"][0]["verdict"] == "supported"
    assert plant["claims"][0]["verdict"] == "supported"


def test_semantic_mode_supports_distributed_news_evidence():
    result = verify_trace(
        RAGTrace(
            query="What terror arrests happened this week?",
            answer=(
                "Three women were arrested this week on terror charges, including two in New York "
                "who were accused of planning to build an explosive device for attacks in the US."
            ),
            contexts=[
                TraceContext(
                    id="terror_arrests",
                    text=(
                        "She's one of three women arrested this week on terror charges. "
                        "On Thursday, Noelle Velentzas and Asia Siddiqui were arrested in New York "
                        "and accused of planning to build an explosive device for attacks in the United States, "
                        "federal prosecutors said."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []


def test_semantic_mode_treats_negated_truth_phrase_as_support():
    result = verify_trace(
        RAGTrace(
            query="Could the Rolling Stone article be considered false by law?",
            answer="The Rolling Stone article presented as fact could potentially be deemed false by the law.",
            contexts=[
                TraceContext(
                    id="defamation",
                    text=(
                        "But the Rolling Stone article certainly purported to be fact, "
                        'and it apparently is not exactly what the law considers "true."'
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["conflicting_facts"] == []


def test_semantic_mode_supports_not_disclosed_paraphrase():
    result = verify_trace(
        RAGTrace(
            query="Were settlement details disclosed?",
            answer="No further details of the settlement have been disclosed.",
            contexts=[
                TraceContext(
                    id="settlement",
                    text=(
                        "She didn't disclose the details of the settlement other than saying that "
                        "one important aspect of it was an apology."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []


def test_semantic_mode_keeps_direct_negation_contradiction():
    result = verify_trace(
        RAGTrace(
            query="Can the document store run pipelines?",
            answer="A Haystack Document Store has a run method.",
            contexts=[
                TraceContext(
                    id="haystack_docs",
                    text="Document Stores do not have a run method and are not pipeline components.",
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "contradicted"
    assert "contradicted_answer" in result["summary"]["failure_types"]


def test_relation_matching_allows_partial_subject_overlap_for_same_object():
    result = verify_trace(
        RAGTrace(
            query="What does Pinecone upsert do?",
            answer="Pinecone upsert writes vectors into a namespace.",
            contexts=[
                TraceContext(
                    id="pinecone_upsert",
                    text=(
                        "The upsert operation writes vectors into a namespace. "
                        "If a new value is upserted for an existing vector ID, it will overwrite the previous value."
                    ),
                )
            ],
            citations=[
                TraceCitation(
                    claim="Pinecone upsert writes vectors into a namespace.",
                    source_id="pinecone_upsert",
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["citation_status"] == "citation_ok"
    assert claim["conflicting_facts"] == []


def test_judge_mode_requires_a_judge_provider(monkeypatch):
    monkeypatch.setenv("CONTEXTTRACE_JUDGE_PROVIDER", "local")
    trace = RAGTrace(
        query="What is the refund policy?",
        answer="Refunds are allowed within 30 days.",
        contexts=[
            TraceContext(
                id="policy",
                text="Customers may request refunds within 30 days of purchase.",
            )
        ],
    )

    with pytest.raises(ValueError, match="requires a judge provider"):
        verify_trace(trace, mode="judge")


def test_judge_mode_overrides_heuristic_support_verdict():
    trace = RAGTrace(
        query="What is the refund policy?",
        answer="Refunds are allowed within 30 days.",
        contexts=[
            TraceContext(
                id="policy",
                text="Customers may request refunds within 30 days of purchase.",
            )
        ],
    )
    judge = StaticJudge(
        [
            JudgeVerdict(
                verdict="unsupported",
                confidence=0.91,
                reason="The evidence says may request, not allowed unconditionally.",
                missing_facts=["allowed unconditionally"],
                provider="unit",
                model="static",
            )
        ]
    )

    result = verify_trace(trace, mode="judge", judge=judge)
    claim = result["claims"][0]

    assert claim["verdict"] == "unsupported"
    assert claim["confidence"] == 0.91
    assert claim["judge"]["provider"] == "unit"
    assert claim["missing_facts"] == ["allowed unconditionally"]
    assert result["summary"]["mode"] == "judge"
    assert result["summary"]["unsupported"] == 1
    assert judge.calls[0]["context_ids"] == ["policy"]
    assert judge.calls[0]["context_texts"] == ["Customers may request refunds within 30 days of purchase."]
    assert judge.calls[0]["context_metadata"][0]["evidence_scope"] == "selected_span"


def test_judge_mode_sees_selected_span_not_full_context():
    trace = RAGTrace(
        query="What is the refund policy?",
        answer="Refunds are allowed within 30 days.",
        contexts=[
            TraceContext(
                id="policy",
                text=(
                    "Shipping takes 5 business days. "
                    "Customers may request refunds within 30 days of purchase. "
                    "Managers review enterprise exceptions separately."
                ),
            )
        ],
    )
    judge = StaticJudge(
        [
            JudgeVerdict(
                verdict="supported",
                confidence=0.93,
                reason="The selected span supports the refund window.",
                matched_facts=["refunds within 30 days"],
                provider="unit",
                model="static",
            )
        ]
    )

    result = verify_trace(trace, mode="judge", judge=judge)

    assert result["claims"][0]["support_status"] == "grounded_by_span"
    assert judge.calls[0]["context_texts"] == ["Customers may request refunds within 30 days of purchase."]
    assert "Shipping takes" not in judge.calls[0]["context_texts"][0]
    assert "Managers review" not in judge.calls[0]["context_texts"][0]


def test_judge_mode_uses_judge_for_cited_source_support():
    trace = RAGTrace(
        query="What is the current refund window?",
        answer="Refunds are allowed within 30 days of purchase.",
        contexts=[
            TraceContext(
                id="policy_2024",
                text="Customers may exchange eligible items within 14 days.",
            ),
            TraceContext(
                id="policy_2026",
                text="Customers may request refunds within 30 days of purchase.",
            ),
        ],
        citations=[
            TraceCitation(
                claim="Refunds are allowed within 30 days of purchase.",
                source_id="policy_2024",
            )
        ],
    )
    judge = StaticJudge(
        [
            JudgeVerdict(
                verdict="supported",
                confidence=0.98,
                reason="The retrieved evidence supports the claim.",
                matched_facts=["Refunds are allowed within 30 days of purchase"],
                provider="unit",
                model="static",
            ),
            JudgeVerdict(
                verdict="unsupported",
                confidence=0.95,
                reason="The cited source discusses exchanges, not refunds.",
                missing_facts=["refunds within 30 days"],
                provider="unit",
                model="static",
            ),
        ]
    )

    result = verify_trace(trace, mode="judge", judge=judge)
    claim = result["claims"][0]

    assert claim["verdict"] == "supported"
    assert claim["citation_status"] == "claim_supported_by_different_source"
    assert [call["context_ids"] for call in judge.calls] == [
        ["policy_2026"],
        ["policy_2024"],
    ]
    assert judge.calls[0]["context_texts"] == ["Customers may request refunds within 30 days of purchase."]
    assert judge.calls[1]["context_texts"] == ["Customers may exchange eligible items within 14 days."]


def test_citation_mismatch_detection():
    result = verify_trace(
        RAGTrace(
            query="What is the current refund window?",
            answer="Refunds are allowed within 30 days of purchase.",
            contexts=[
                TraceContext(
                    id="policy_2024",
                    text="Customers may exchange eligible items within 14 days.",
                ),
                TraceContext(
                    id="policy_2026",
                    text="Customers may request refunds within 30 days of purchase.",
                ),
            ],
            citations=[
                TraceCitation(
                    claim="Refunds are allowed within 30 days of purchase.",
                    source_id="policy_2024",
                )
            ],
        )
    )

    assert result["claims"][0]["verdict"] == "supported"
    assert result["claims"][0]["best_context_id"] == "policy_2026"
    assert result["claims"][0]["citation_status"] == "claim_supported_by_different_source"
    assert result["claims"][0]["root_cause"]["label"] == "wrong_source_cited"
    assert result["summary"]["primary_root_cause"] == "wrong_source_cited"
    assert result["summary"]["citation_mismatches"] == 1
    assert result["summary"]["failure_type"] == "citation_mismatch"


def test_citation_requires_cited_source_to_cover_all_required_facts():
    result = verify_trace(
        RAGTrace(
            query="How does the evaluator store traces?",
            answer=(
                "The evaluator calls your endpoint for each question and saves traces "
                "in .contexttrace/contexttrace.db."
            ),
            contexts=[
                TraceContext(
                    id="eval_steps",
                    text=(
                        "The evaluator will call your endpoint for each question, extract the answer, "
                        "contexts, and citations, and create local ContextTrace traces."
                    ),
                ),
                TraceContext(
                    id="storage",
                    text="The evaluator will save traces in .contexttrace/contexttrace.db.",
                ),
            ],
            citations=[
                TraceCitation(
                    claim="The evaluator calls your endpoint for each question and saves traces in .contexttrace/contexttrace.db.",
                    source_id="eval_steps",
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["citation_status"] == "cited_source_does_not_support_claim"
    assert len(claim["supporting_spans"]) >= 2
    assert ".contexttrace/contexttrace.db" in claim["matched_facts"]


def test_contradicted_claim_root_cause_is_conflicting_contexts():
    result = verify_trace(
        RAGTrace(
            query="Can customers request refunds within 30 days?",
            answer="Customers cannot request refunds within 30 days.",
            contexts=[
                TraceContext(
                    id="policy",
                    text="Customers may request refunds within 30 days of purchase.",
                )
            ],
        )
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "contradicted"
    assert claim["root_cause"]["label"] == "conflicting_contexts"
    assert result["summary"]["primary_root_cause"] == "conflicting_contexts"


def test_version_contradiction_without_stale_source_is_conflicting_contexts():
    result = verify_trace(
        RAGTrace(
            query="Which release added local claim-level evidence verification?",
            answer="ContextTrace v0.1.0 adds local claim-level evidence verification for portable RAG traces.",
            contexts=[
                TraceContext(
                    id="release_v020",
                    text="ContextTrace v0.2.0 adds local claim-level evidence verification for portable RAG traces.",
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "contradicted"
    assert claim["root_cause"]["label"] == "conflicting_contexts"
    assert result["summary"]["primary_root_cause"] == "conflicting_contexts"


@pytest.mark.parametrize(
    ("answer", "context"),
    [
        (
            "The Eiffel Tower is in Berlin.",
            "The Eiffel Tower is in Paris. Berlin is in Germany.",
        ),
        (
            "Alexander Dumas discovered penicillin.",
            "Alexander Fleming discovered penicillin. Alexandre Dumas was a novelist.",
        ),
        (
            "A causes B.",
            "B causes A.",
        ),
    ],
)
def test_relation_conflicts_are_not_supported_by_token_overlap(answer, context):
    result = verify_trace(
        RAGTrace(
            query="Check the factual relation.",
            answer=answer,
            contexts=[TraceContext(id="evidence", text=context)],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "contradicted"
    assert claim["conflicting_facts"] == [answer.rstrip(".")]
    assert "contradicted_answer" in result["summary"]["failure_types"]


def test_should_abstain_detection_when_contexts_do_not_support_answer():
    result = verify_trace(
        RAGTrace(
            query="What refund exception applies to VIP customers?",
            answer="VIP customers receive cash refunds up to 90 days after purchase.",
            contexts=[
                TraceContext(
                    id="shipping",
                    text="Standard shipping takes 3 to 5 business days.",
                )
            ],
        )
    )

    assert result["abstention"]["should_abstain"] is True
    assert "does not appear" in result["abstention"]["reason"]
    assert result["summary"]["failure_type"] == "should_have_abstained"
    assert result["summary"]["primary_root_cause"] == "should_have_abstained"
    assert result["claims"][0]["root_cause"]["label"] == "should_have_abstained"


def test_report_generation(tmp_path):
    trace = RAGTrace(
        query="What is the refund policy?",
        answer="Refunds are allowed within 30 days.",
        contexts=[
            TraceContext(
                id="policy",
                text="Customers may request refunds within 30 days of purchase.",
            )
        ],
    )
    result = verify_trace(trace)
    report_path = tmp_path / "verify.html"

    written = VerifyReportGenerator().generate(result, trace, path=str(report_path))

    assert written == str(report_path)
    html = report_path.read_text(encoding="utf-8")
    assert "ContextTrace Verification Report" in html
    assert "Reliability Summary" in html
    assert "Claim Grounding Overview" in html
    assert "Grounded means supported by the selected evidence span" in html
    assert "grounded_by_span" in html
    assert "not_assessed" in html
    assert "Raw JSON Summary" in html
    assert "<mark>refunds</mark>" in html
    assert "Matched facts" in html
    assert "Evidence span" in html
    assert "Supporting spans" in html
    assert "Source Trust & Freshness" in html
    assert "Root Cause Diagnosis" in html


def test_verify_cli_json_and_report(tmp_path, capsys):
    trace_path = tmp_path / "trace.json"
    report_path = tmp_path / "report.html"
    trace_path.write_text(
        json.dumps(
            {
                "query": "What is the refund policy?",
                "answer": "Refunds are allowed within 30 days.",
                "contexts": [
                    {
                        "id": "policy",
                        "text": "Customers may request refunds within 30 days of purchase.",
                    }
                ],
                "citations": [
                    {
                        "claim": "Refunds are allowed within 30 days.",
                        "source_id": "policy",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["verify", str(trace_path), "--json", "--report", "--out", str(report_path)]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["summary"]["support_rate"] == 1.0
    assert output["claims"][0]["citation_status"] == "citation_ok"
    assert report_path.exists()


def test_verify_demo_cli_defaults_to_unsupported_claim(capsys):
    assert main(["verify-demo", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["metadata"]["run_id"] == "golden_unsupported_claim"
    assert output["summary"]["unsupported_claim_rate"] == 1.0
    assert output["summary"]["failure_type"] == "should_have_abstained"
    assert output["claims"][0]["verdict"] == "unsupported"


def test_verify_demo_cli_named_report(tmp_path, capsys):
    report_path = tmp_path / "citation-demo.html"

    assert main(["verify-demo", "citation_mismatch", "--report", "--out", str(report_path)]) == 0

    output = capsys.readouterr().out
    assert "Failure type: citation_mismatch" in output
    assert report_path.exists()
    html = report_path.read_text(encoding="utf-8")
    assert "claim_supported_by_different_source" in html
    assert "Best supporting context: policy_2026" in html


def test_verify_demo_cli_unknown_name(capsys):
    assert main(["verify-demo", "missing_demo"]) == 1

    assert "Available demos" in capsys.readouterr().err


def test_verify_cli_fail_on_unsupported_sets_exit_code(tmp_path, capsys):
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "query": "How long does refund processing take?",
                "answer": "Refunds are processed within 5 business days.",
                "contexts": [
                    {
                        "id": "policy",
                        "text": "Customers may request refunds within 30 days of purchase.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["verify", str(trace_path), "--fail-on", "unsupported"]) == 1

    assert "unsupported claim detected" in capsys.readouterr().err


def test_verify_cli_accepts_local_ml_mode(tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("CONTEXTTRACE_LOCAL_ML_MODEL_PATH", raising=False)
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "query": "Where does ContextTrace store traces?",
                "answer": "ContextTrace stores traces in .contexttrace/contexttrace.db.",
                "contexts": [
                    {
                        "id": "docs/local-mode.md",
                        "text": "ContextTrace stores traces in .contexttrace/contexttrace.db.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["verify", str(trace_path), "--mode", "local_ml", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["summary"]["mode"] == "local_ml"
    assert output["claims"][0]["verdict"] == "supported"


def test_verify_cli_judge_mode_requires_provider(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("CONTEXTTRACE_JUDGE_PROVIDER", "local")
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "query": "What is the refund policy?",
                "answer": "Refunds are allowed within 30 days.",
                "contexts": [
                    {
                        "id": "policy",
                        "text": "Customers may request refunds within 30 days of purchase.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["verify", str(trace_path), "--mode", "judge"]) == 1

    assert "CONTEXTTRACE_JUDGE_PROVIDER=ollama" in capsys.readouterr().err


def test_verify_cli_blocks_remote_judge_when_local_only(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("CONTEXTTRACE_JUDGE_PROVIDER", "openai")
    monkeypatch.setenv("CONTEXTTRACE_JUDGE_API_KEY", "test-key")
    trace_path = tmp_path / "trace.json"
    trace_path.write_text(
        json.dumps(
            {
                "query": "What is the refund policy?",
                "answer": "Refunds are allowed within 30 days.",
                "contexts": [
                    {
                        "id": "policy",
                        "text": "Customers may request refunds within 30 days of purchase.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    assert main(["verify", str(trace_path), "--mode", "judge"]) == 1

    assert "only allows localhost judge URLs" in capsys.readouterr().err


def test_verify_demo_fail_on_any_failure(capsys):
    assert main(["verify-demo", "supported_answer", "--fail-on", "any_failure"]) == 0
    capsys.readouterr()

    assert main(["verify-demo", "citation_mismatch", "--fail-on", "any_failure"]) == 1
    assert "verification failure detected" in capsys.readouterr().err


def test_verify_benchmark_semantic_mode_scores_curated_cases():
    result = run_verify_benchmark(mode="semantic")

    assert result["mode"] == "semantic"
    assert result["case_source"] == "real ContextTrace repository docs and release artifacts"
    assert result["cases"] >= 5
    assert result["exact_match_rate"] >= 0.8
    assert result["verdict_match_rate"] >= 0.8
    assert result["citation_match_rate"] >= 0.8
    assert result["abstention_match_rate"] >= 0.8
    assert result["per_label"]["unsupported_answer"]["recall"] >= 0.8
    assert result["per_label"]["partial_support"]["recall"] >= 0.8
    assert any(row["source"].startswith("docs/") for row in result["rows"])


def test_verify_benchmark_external_case_set_scores_real_oss_cases():
    result = run_verify_benchmark(mode="semantic", case_set="external")

    assert result["case_set"] == "external"
    assert result["case_source"] == "real external OSS docs and public GitHub issues"
    assert result["cases"] >= 10
    assert result["exact_match_rate"] >= 0.8
    assert result["verdict_match_rate"] >= 0.8
    assert result["citation_match_rate"] >= 0.8
    assert any("qdrant.tech" in row["source"] for row in result["rows"])
    assert any("github.com/chroma-core" in row["source"] for row in result["rows"])


def test_verify_benchmark_public_holdout_case_set_is_separate():
    result = run_verify_benchmark(mode="semantic", case_set="public_holdout")
    all_result = run_verify_benchmark(mode="semantic", case_set="all")

    assert result["case_set"] == "public_holdout"
    assert result["case_source"] == "curated public holdout docs from RAG, vector database, observability, and evaluator projects"
    assert result["cases"] >= 30
    assert all_result["case_set"] == "all"
    assert not any(str(row["id"]).startswith("holdout_") for row in all_result["rows"])
    assert any("opentelemetry.io" in row["source"] for row in result["rows"])
    assert any("docs.weaviate.io" in row["source"] for row in result["rows"])
    assert any("docs.pinecone.io" in row["source"] for row in result["rows"])
    assert any("deepeval.com" in row["source"] for row in result["rows"])
    assert result["citation_match_rate"] == 1.0
    assert result["exact_match_rate"] >= 0.9


def test_verify_benchmark_cli_json(capsys):
    assert main(["verify-benchmark", "--mode", "semantic", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["mode"] == "semantic"
    assert output["case_source"] == "real ContextTrace repository docs and release artifacts"
    assert output["per_label"]["no_failure_detected"]["precision"] >= 0.8


def test_verify_benchmark_cli_external_case_set_json(capsys):
    assert main(["verify-benchmark", "--case-set", "external", "--mode", "semantic", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["case_set"] == "external"
    assert output["case_source"] == "real external OSS docs and public GitHub issues"


def test_verify_benchmark_cli_public_holdout_case_set_json(capsys):
    assert main(["verify-benchmark", "--case-set", "public_holdout", "--mode", "semantic", "--json"]) == 0

    output = json.loads(capsys.readouterr().out)
    assert output["case_set"] == "public_holdout"
    assert output["cases"] >= 30


def test_verify_benchmark_cli_report(tmp_path, capsys):
    report_path = tmp_path / "benchmark.html"

    assert main(["verify-benchmark", "--mode", "semantic", "--report", "--out", str(report_path)]) == 0

    output = capsys.readouterr().out
    assert "Case source: real ContextTrace repository docs and release artifacts" in output
    assert "Report: %s" % report_path in output
    html = report_path.read_text(encoding="utf-8")
    assert "ContextTrace Verification Benchmark" in html
    assert "Usefulness Summary" in html
    assert "Misses To Inspect" in html
    assert "Matched facts" in html
    assert "Missing facts" in html
