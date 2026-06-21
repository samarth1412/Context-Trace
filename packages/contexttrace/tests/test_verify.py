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


def test_claim_extraction_strips_generated_summary_prefixes():
    claims = extract_claims(
        "Here's a summary of the article within 109 words: On Big Brother 25, "
        "the houseguests have regrets about evicting Cameron Hardin."
    )

    assert [claim.text for claim in claims] == [
        "On Big Brother 25, the houseguests have regrets about evicting Cameron Hardin."
    ]


def test_claim_extraction_strips_generated_summary_prefix_variants():
    claims = extract_claims("Here's the summary in 65 words: Nelly was arrested on drug charges.")

    assert [claim.text for claim in claims] == ["Nelly was arrested on drug charges."]


def test_claim_extraction_strips_structured_overview_prefixes():
    claims = extract_claims(
        "Based on the provided structured data in JSON format: Tiburon Tavern is a local dive bar located in Santa Barbara."
    )

    assert [claim.text for claim in claims] == [
        "Tiburon Tavern is a local dive bar located in Santa Barbara."
    ]


def test_claim_extraction_strips_passage_boilerplate_prefixes():
    claims = extract_claims(
        "Based on the given passages, PSA levels refer to the amount of prostate-specific antigen present in a man's blood."
    )

    assert [claim.text for claim in claims] == [
        "PSA levels refer to the amount of prostate-specific antigen present in a man's blood."
    ]


def test_claim_extraction_skips_numbered_list_markers_after_boilerplate():
    claims = extract_claims(
        "Based on the given passages, the proper way to dispose of a worn US flag is to either: "
        "1. Burn it in a peaceful manner. 2. Perform a proper ceremony."
    )

    assert [claim.text for claim in claims] == [
        "Burn it in a peaceful manner.",
        "Perform a proper ceremony.",
    ]


def test_claim_extraction_strips_how_to_boilerplate_prefixes():
    claims = extract_claims(
        "Sure, here's how to clean the dryer vent based on the given passages: "
        "To clean the dryer vent, you should follow these steps: 1. Locate the dryer vent cover."
    )

    assert [claim.text for claim in claims] == ["Locate the dryer vent cover."]


def test_claim_extraction_skips_option_answer_meta_sentence():
    claims = extract_claims(
        "Therefore, the answer is: \"Option 1 or Option 2.\" Burn it in a peaceful manner."
    )

    assert [claim.text for claim in claims] == ["Burn it in a peaceful manner."]


def test_claim_extraction_skips_orphan_option_marker_sentence():
    claims = extract_claims('Therefore, the answer is: "Option 1 or Option 2."')

    assert claims == []


def test_claim_extraction_strips_discourse_prefixes():
    conclusion_claims = extract_claims(
        "In conclusion, the recommended method involves using identical frames and attaching small hinges."
    )
    passage_claims = extract_claims(
        "(Passage 3) Therefore, to grill pork chops, preheat the grill and season the pork chops."
    )

    assert [claim.text for claim in conclusion_claims] == [
        "the recommended method involves using identical frames and attaching small hinges."
    ]
    assert [claim.text for claim in passage_claims] == [
        "to grill pork chops, preheat the grill and season the pork chops."
    ]


def test_claim_extraction_skips_source_availability_boilerplate():
    claims = extract_claims(
        "The passages do not provide information on the size or weight of the roast, so cooking times may vary. "
        "Unable to answer based on given passages. If you have any further questions or concerns, please let me know!"
    )

    assert claims == []


def test_claim_extraction_keeps_passage_specific_absence_claims():
    claims = extract_claims("Passage 3 does not provide information about the difference between sirloin and porterhouse.")

    assert [claim.text for claim in claims] == [
        "Passage 3 does not provide information about the difference between sirloin and porterhouse."
    ]


def test_claim_extraction_preserves_us_abbreviation_in_boilerplate_prefix():
    claims = extract_claims(
        "Here's a brief answer to the question \"change of address u.s. postal service\" based on the given passages: "
        "To change your address with the U.S. Postal Service, visit the USPS website."
    )

    assert [claim.text for claim in claims] == [
        "To change your address with the U.S. Postal Service, visit the USPS website."
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


def test_fact_matching_splits_while_contrast_claims():
    match = compare_facts(
        "Adverb clauses modify verbs, adjectives, or another adverbs, while adjective clauses modify nouns or pronouns.",
        "An adverb clause is a dependent clause that modifies a verb, adjective or another adverb.",
        mode="semantic",
    )

    assert match.matched_facts == ["Adverb clauses modify verbs, adjectives, or another adverbs"]
    assert match.missing_facts == ["adjective clauses modify nouns or pronouns"]


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


def test_high_overlap_missing_fact_is_not_marked_supported():
    result = verify_trace(
        RAGTrace(
            query="What is the trial status?",
            answer="The first clinical trial focusing on recurrent ovarian cancer is currently underway.",
            contexts=[
                TraceContext(
                    id="trial",
                    text=(
                        "The first clinical trial will focus on recurrent ovarian cancer, "
                        "with human trials expected to begin within five years."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "contradicted"
    assert claim["conflicting_fact_details"][0]["type"] == "temporal_status"
    assert "contradicted_answer" in result["summary"]["failure_types"]


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


def test_semantic_mode_supports_numbered_list_items_without_include_marker():
    result = verify_trace(
        RAGTrace(
            query="What are early signs of pregnancy?",
            answer=(
                "The earliest signs and symptoms of pregnancy include mood swings, "
                "dizziness, bloating, spotting, cramping, and nausea with or without vomiting."
            ),
            contexts=[
                TraceContext(
                    id="pregnancy_signs",
                    text=(
                        "1 Mood swings. The flood of hormones in your body in early pregnancy can make "
                        "you unusually emotional and weepy. Mood swings also are common. "
                        "4 Dizziness. Pregnancy causes your blood vessels to dilate and your blood "
                        "pressure to drop. As a result, you might feel lightheaded or dizzy. "
                        "The earliest signs of pregnancy can include bloating, spotting, cramping, "
                        "and nausea with or without vomiting."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []


def test_semantic_mode_supports_list_items_with_generic_gerund_heads():
    result = verify_trace(
        RAGTrace(
            query="What are benefits of cupping massage?",
            answer=(
                "The benefits of cupping massage include eliminating toxins from the body, "
                "improving circulation, providing pain relief, increasing range of motion "
                "and flexibility, and decreasing anxiety."
            ),
            contexts=[
                TraceContext(
                    id="cupping",
                    text=(
                        "Some of the cupping massage benefits include the following: "
                        "1 Eliminates toxins: A cupping massage can get rid of toxins from the body. "
                        "2 Improved circulation: Increased blood circulation can also be brought about by cupping. "
                        "3 Pain relief: A cupping massage helps reduce inflammation of tissues. "
                        "4 Range of motion and flexibility can improve after treatment. "
                        "5 Decreases anxiety."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []


def test_semantic_mode_allows_distributed_prevent_by_support():
    result = verify_trace(
        RAGTrace(
            query="How can I prevent birds from nesting on a porch?",
            answer=(
                "You can prevent birds from building nests on your porch by attaching bird netting "
                "to the eaves around the perimeter of your porch and the top of the porch if it has open rafters."
            ),
            contexts=[
                TraceContext(
                    id="bird_nesting",
                    text=(
                        "Attach bird netting to the eaves around the perimeter of your porch with a staple gun. "
                        "If your porch has open rafters, use the staple gun to attach the netting to the top of the porch. "
                        "The netting keeps the birds from reaching those spaces they often choose to build their nests."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []


def test_semantic_mode_supports_news_event_catalog_items():
    result = verify_trace(
        RAGTrace(
            query="What will National Park Week include?",
            answer=(
                "National Park Week will include various activities and events, "
                "and people are encouraged to share their experiences using #FindYourPark."
            ),
            contexts=[
                TraceContext(
                    id="national_park_week",
                    text=(
                        "It is all part of National Park Week, happening April 18 through April 26. "
                        "Check out night-time astronomy parties, daytime Revolutionary War programs, "
                        "Earth Day parties and family-friendly Junior Ranger activities at national park sites. "
                        "The park service wants people to share their stories using the hashtag #FindYourPark."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []


def test_semantic_mode_supports_distributed_appositive_relation_summary():
    result = verify_trace(
        RAGTrace(
            query="What legal battle is Sofia Vergara in?",
            answer=(
                "Sofia Vergara, actress and star of Modern Family, is in a legal battle "
                "with her ex-fiance Nick Loeb over two frozen embryos they created together."
            ),
            contexts=[
                TraceContext(
                    id="vergara_embryos",
                    text=(
                        "Sofia Vergara is playing defense in a legal battle initiated by her ex-fiance. "
                        "The 42-year-old actress and star of the hit TV sitcom Modern Family split from "
                        "businessman Nick Loeb in May 2014. Court papers allege the couple created the "
                        "embryos while they were engaged."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []


def test_semantic_mode_supports_news_likely_and_passed_away_paraphrases():
    result = verify_trace(
        RAGTrace(
            query="What happened?",
            answer=(
                "Lauren Hill, a 19-year-old who fought against brain cancer and whose story inspired many, "
                "has passed away. Hostilities are expected to resume soon."
            ),
            contexts=[
                TraceContext(
                    id="paraphrases",
                    text=(
                        "Lauren Hill, who took her inspirational fight against brain cancer onto the "
                        "basketball court and into the hearts of many, has died at age 19. "
                        "Hostilities are likely to resume before the day is out."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    assert [claim["verdict"] for claim in result["claims"]] == ["supported", "supported"]
    assert all(not claim["missing_facts"] for claim in result["claims"])


def test_semantic_mode_supports_structured_negated_parking_lists():
    result = verify_trace(
        RAGTrace(
            query="What parking is available?",
            answer="The business parking options include a garage but not street parking, validated parking, a lot, or valet services.",
            contexts=[
                TraceContext(
                    id="parking_json",
                    text=json.dumps(
                        {
                            "attributes": {
                                "BusinessParking": {
                                    "garage": True,
                                    "street": False,
                                    "validated": False,
                                    "lot": False,
                                    "valet": False,
                                }
                            }
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []
    assert "contradicted_answer" not in result["summary"]["failure_types"]


def test_semantic_mode_requires_death_count_identity_in_one_unit():
    result = verify_trace(
        RAGTrace(
            query="What happened on Everest?",
            answer="A deadly avalanche in 2014 killed 16 Sherpas and closed the climbing season.",
            contexts=[
                TraceContext(
                    id="everest",
                    text=(
                        "In 2014, the Nepal climbing season ended after a piece of glacial ice fell, "
                        "unleashing an avalanche that killed 16 Nepalis who had just finished their morning prayers. "
                        "The deaths launched fierce debates about the risks faced by the Sherpas."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] != "supported"
    assert claim["missing_facts"]


def test_semantic_mode_supports_news_summary_across_paraphrased_spans():
    result = verify_trace(
        RAGTrace(
            query="What did the trailer show?",
            answer=(
                "The trailer features footage of Superman and Batman facing off, "
                "along with overlapping commentary from various voices."
            ),
            contexts=[
                TraceContext(
                    id="batman_trailer",
                    text=(
                        "The trailer begins with a commentator's voice asking whether the most "
                        "powerful man in the world should be a figure of controversy. "
                        "As footage of Superman plays, numerous commentators' voices overlap "
                        "one another with their opinions of the superheroes. "
                        "A masked Batman appears, followed by the two superheroes coming face to face."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []
    assert len(claim["supporting_spans"]) >= 2
    assert result["summary"]["failure_type"] == "no_failure_detected"


def test_semantic_mode_supports_distributed_odor_detection_paraphrase():
    result = verify_trace(
        RAGTrace(
            query="What happened during the traffic stop?",
            answer=(
                "During a routine traffic stop, state troopers detected the smell "
                "of marijuana coming from Nelly's private bus."
            ),
            contexts=[
                TraceContext(
                    id="nelly_arrest",
                    text=(
                        "Hip-hop star Nelly has been arrested on drug charges in Tennessee "
                        "after a state trooper pulled over the private bus in which he was traveling. "
                        "The state trooper stopped the bus carrying Nelly and five other people. "
                        'The trooper noticed an odor of marijuana emitting from the bus.'
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []
    assert result["summary"]["failure_type"] == "no_failure_detected"


def test_semantic_mode_supports_measurement_paraphrase():
    result = verify_trace(
        RAGTrace(
            query="What can children learn from water play?",
            answer=(
                "In math, they learn about measurement by determining the amount of water "
                "that fits into a bucket, and concepts of more and less by comparing water "
                "levels in different buckets."
            ),
            contexts=[
                TraceContext(
                    id="water_play",
                    text=(
                        "In math, children are able to learn about measuring a certain amount "
                        "of water into a bucket, more and less by filling one bucket with more "
                        "water and one bucket with less water."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []
    assert result["summary"]["failure_type"] == "no_failure_detected"


def test_semantic_mode_does_not_mark_appositive_relation_support_as_conflict():
    result = verify_trace(
        RAGTrace(
            query="What is Loeb suing over?",
            answer=(
                "Loeb is suing Vergara to prevent her from destroying the embryos, "
                "which were conceived through in vitro fertilization in 2013."
            ),
            contexts=[
                TraceContext(
                    id="embryos",
                    text=(
                        "Loeb is suing the Colombian-born actress in Los Angeles to prevent "
                        "Vergara from destroying their two embryos conceived through in vitro "
                        "fertilization in November 2013."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["conflicting_facts"] == []


def test_semantic_mode_does_not_mark_generic_subject_relation_support_as_conflict():
    result = verify_trace(
        RAGTrace(
            query="What did the experience lead to?",
            answer=(
                'The experience led to Jiang writing a book called "Rejection Proof", '
                "which is part self-help and part motivational/autobiography."
            ),
            contexts=[
                TraceContext(
                    id="rejection",
                    text=(
                        "This led to his writing his book called Rejection Proof, part "
                        "self-help and part motivational/autobiography, which is being "
                        "released this week."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["conflicting_facts"] == []


def test_semantic_mode_requires_record_category_in_same_evidence_unit():
    result = verify_trace(
        RAGTrace(
            query="What record did Cirie Fields set?",
            answer="Cirie Fields set a record for most times nominated for eviction.",
            contexts=[
                TraceContext(
                    id="big_brother",
                    text=(
                        "More from the world of Big Brother. Cirie Fields just set a Big Brother record. "
                        "And then it was time for another Big Brother Eviction Ceremony."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] != "supported"
    assert claim["missing_facts"]


def test_semantic_mode_treats_not_happy_as_not_pleased_support():
    result = verify_trace(
        RAGTrace(
            query="How did Turkey react?",
            answer="Turkey was not pleased with the Pope's remarks.",
            contexts=[
                TraceContext(
                    id="pope_turkey",
                    text=(
                        "In a tweet Sunday, Turkey's Foreign Minister called the Pope's use "
                        'of the word "unacceptable." New or not, Turkey was not happy.'
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["conflicting_facts"] == []
    assert "contradicted_answer" not in result["summary"]["failure_types"]


def test_semantic_mode_does_not_contradict_uncertain_mixed_legal_evidence():
    result = verify_trace(
        RAGTrace(
            query="Would the fraternity members have individualized injury?",
            answer=(
                'While the "small group" exception may apply, it is unclear whether '
                "individual members of the fraternity have suffered an individualized injury."
            ),
            contexts=[
                TraceContext(
                    id="defamation_analysis",
                    text=(
                        'Phi Kappa Psi would likely argue that the "small group" exception fits. '
                        "Even if individual members were not identified by name, the story has "
                        "been imputed directly to individual members, who have suffered by their "
                        "association with the group. On the other hand, Rolling Stone's lawyers "
                        "would likely argue that the group is so large and fluid that the members "
                        "have suffered no individualized injury."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["conflicting_facts"] == []
    assert "contradicted_answer" not in result["summary"]["failure_types"]


def test_semantic_mode_uses_structured_json_attributes_for_support():
    result = verify_trace(
        RAGTrace(
            query="What amenities does the restaurant offer?",
            answer="The restaurant offers outdoor seating, takeout, and WiFi.",
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "attributes": {
                                "OutdoorSeating": True,
                                "RestaurantsTakeOut": True,
                                "WiFi": "free",
                            },
                            "categories": "Mexican, Restaurants",
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []
    assert claim["conflicting_facts"] == []


def test_semantic_mode_uses_structured_json_category_phrases_for_support():
    result = verify_trace(
        RAGTrace(
            query="What does the cafe offer?",
            answer="It offers a variety of cuisines including Italian, Mediterranean, and cafe-style dishes.",
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "categories": "Italian, Cafes, Mediterranean, Restaurants",
                            "name": "Cafe Lido",
                            "city": "Santa Barbara",
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []


def test_semantic_mode_uses_structured_json_amenity_aliases_for_support():
    result = verify_trace(
        RAGTrace(
            query="What amenities are available?",
            answer=(
                "Notable amenities include business parking with garage and street options, "
                "reservations, outdoor seating, takeaway service, and suitability for groups."
            ),
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "attributes": {
                                "BusinessParking": {
                                    "garage": True,
                                    "lot": False,
                                    "street": True,
                                    "valet": False,
                                    "validated": False,
                                },
                                "OutdoorSeating": True,
                                "RestaurantsGoodForGroups": True,
                                "RestaurantsReservations": True,
                                "RestaurantsTakeOut": True,
                            }
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []
    assert claim["conflicting_facts"] == []


def test_semantic_mode_uses_structured_json_hours_for_support():
    daily = verify_trace(
        RAGTrace(
            query="When is the restaurant open?",
            answer="The restaurant is open from 11:00 am to 9:00 pm every day of the week.",
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "hours": {
                                "Monday": "11:0-21:0",
                                "Tuesday": "11:0-21:0",
                                "Wednesday": "11:0-21:0",
                                "Thursday": "11:0-21:0",
                                "Friday": "11:0-21:0",
                                "Saturday": "11:0-21:0",
                                "Sunday": "11:0-21:0",
                            }
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )
    extended_weekend = verify_trace(
        RAGTrace(
            query="When is the brewpub open?",
            answer=(
                "It operates from 11:30 to 19:30 from Monday to Sunday, "
                "with extended hours until 20:00 on Fridays and Saturdays."
            ),
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "hours": {
                                "Monday": "11:30-19:30",
                                "Tuesday": "11:30-19:30",
                                "Wednesday": "11:30-19:30",
                                "Thursday": "11:30-19:30",
                                "Friday": "11:30-20:0",
                                "Saturday": "11:30-20:0",
                                "Sunday": "11:30-19:30",
                            }
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    assert daily["claims"][0]["verdict"] == "supported"
    assert daily["claims"][0]["conflicting_facts"] == []
    assert extended_weekend["claims"][0]["verdict"] == "supported"
    assert extended_weekend["claims"][0]["conflicting_facts"] == []


def test_semantic_mode_uses_structured_json_day_specific_hours_for_support():
    result = verify_trace(
        RAGTrace(
            query="When does the club operate?",
            answer=(
                "The business operates on Tuesdays from 6:00 PM to 1:00 AM, "
                "Fridays from 6:00 PM to 11:00 PM, and Saturdays from 1:00 PM to 11:00 PM."
            ),
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "hours": {
                                "Tuesday": "18:0-1:0",
                                "Friday": "18:0-23:0",
                                "Saturday": "13:0-23:0",
                            }
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["conflicting_facts"] == []


def test_semantic_mode_uses_structured_json_weekday_and_saturday_hours_for_support():
    result = verify_trace(
        RAGTrace(
            query="When is the bakery open?",
            answer=(
                "The bakery is open from 6:00 am to 5:30 pm from Monday to Friday "
                "and from 7:00 am to 4:00 pm on Saturdays."
            ),
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "hours": {
                                "Monday": "6:0-17:30",
                                "Tuesday": "6:0-17:30",
                                "Wednesday": "6:0-17:30",
                                "Thursday": "6:0-17:30",
                                "Friday": "6:0-17:30",
                                "Saturday": "7:0-16:0",
                            }
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []
    assert claim["conflicting_facts"] == []


def test_semantic_mode_uses_structured_review_info_for_mixed_sentiment_support():
    result = verify_trace(
        RAGTrace(
            query="What do reviews say?",
            answer=(
                "Customer reviews highlight mixed feelings. Some patrons praised the Korean chicken wings, "
                "while others complained about slow service."
            ),
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "review_info": [
                                {
                                    "review_stars": 5,
                                    "review_text": "The Korean chicken wings were excellent and the new menu was great.",
                                },
                                {
                                    "review_stars": 1,
                                    "review_text": "The service was slow and disappointing.",
                                },
                            ]
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    assert [claim["verdict"] for claim in result["claims"]] == ["supported", "supported"]
    assert all(claim["missing_facts"] == [] for claim in result["claims"])
    assert all(claim["conflicting_facts"] == [] for claim in result["claims"])


def test_semantic_mode_supports_structured_absent_information_claims():
    result = verify_trace(
        RAGTrace(
            query="Which attributes are known?",
            answer=(
                "The provided structured data does not include information about restaurant reservations, "
                "takeout service, WiFi availability, or whether the restaurant is good for groups."
            ),
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps({"attributes": {}, "categories": "Bakeries, Food"}),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []
    assert claim["conflicting_facts"] == []


def test_semantic_mode_supports_mixed_polarity_structured_parking_claims():
    result = verify_trace(
        RAGTrace(
            query="What parking is available?",
            answer=(
                "The business does not provide garage or valet parking, "
                "but street parking and a parking lot are available."
            ),
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "attributes": {
                                "BusinessParking": {
                                    "garage": False,
                                    "lot": True,
                                    "street": True,
                                    "valet": False,
                                }
                            }
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []
    assert claim["conflicting_facts"] == []


def test_semantic_mode_does_not_leak_negation_across_but_or_though_structured_claims():
    result = verify_trace(
        RAGTrace(
            query="What does the restaurant offer?",
            answer=(
                "It is a casual dining spot that does not accept reservations but offers outdoor seating "
                "and is suitable for groups. However, they do not provide WiFi and only accept cash payments, "
                "though an ATM is available onsite."
            ),
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "attributes": {
                                "Ambience": {"casual": True},
                                "OutdoorSeating": True,
                                "RestaurantsGoodForGroups": True,
                                "RestaurantsReservations": False,
                                "WiFi": "no",
                            },
                            "review_info": [
                                {
                                    "review_stars": 4,
                                    "review_text": "Only cash but don't worry, there's an ATM there!",
                                }
                            ],
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    assert [claim["verdict"] for claim in result["claims"]] == ["supported", "supported"]
    assert all(claim["missing_facts"] == [] for claim in result["claims"])
    assert all(claim["conflicting_facts"] == [] for claim in result["claims"])


def test_semantic_mode_supports_structured_variable_closing_hours():
    result = verify_trace(
        RAGTrace(
            query="When is the restaurant open?",
            answer=(
                "The restaurant operates from 10:00 am every day, with closing hours varying between "
                "4:00 pm and 8:00 pm depending on the day."
            ),
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "hours": {
                                "Monday": "10:0-16:0",
                                "Tuesday": "10:0-19:0",
                                "Wednesday": "10:0-19:0",
                                "Thursday": "10:0-19:0",
                                "Friday": "10:0-20:0",
                                "Saturday": "10:0-20:0",
                                "Sunday": "10:0-17:0",
                            }
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []
    assert claim["conflicting_facts"] == []


def test_semantic_mode_supports_structured_review_paraphrases():
    result = verify_trace(
        RAGTrace(
            query="What do customer reviews say?",
            answer=(
                "It specializes in Indian cuisine and is known for its good food and friendly staff. "
                "The lunch buffet and dinner options have been particularly appreciated. "
                "There is also a small salad bar, which seems to be a favorite among the customers. "
                "On the other hand, another customer expressed disappointment with their experience. "
                "They mentioned changes in the sandwich menu and a lack of pastry options. "
                "They also complained about receiving the wrong sandwich and the high prices. "
                "Reviewers have noted that the restaurant can be busy, particularly during golf events at the nearby course."
            ),
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "categories": "Indian, Restaurants",
                            "review_info": [
                                {
                                    "review_stars": 5,
                                    "review_text": (
                                        "I had a hunkering for good Indian food. The food here was really good, "
                                        "fresh, the people were nice, lunch buffet and dinner was good and they "
                                        "had a little salad bar my favorite part."
                                    ),
                                },
                                {
                                    "review_stars": 1,
                                    "review_text": (
                                        "What a disappointment! The sandwich menu changed and not a wide selection "
                                        "of pastries anymore. I got the wrong sandwich and it was too expensive."
                                    ),
                                },
                                {
                                    "review_stars": 4,
                                    "review_text": (
                                        "That morning, there was a golf event scheduled at the course, "
                                        "and there were more people than normal."
                                    ),
                                },
                            ],
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    assert all(claim["verdict"] == "supported" for claim in result["claims"])
    assert all(claim["missing_facts"] == [] for claim in result["claims"])
    assert all(claim["conflicting_facts"] == [] for claim in result["claims"])


def test_semantic_mode_supports_structured_review_domain_paraphrases():
    result = verify_trace(
        RAGTrace(
            query="What themes do the reviews mention?",
            answer=(
                "Customer reviews highlight concerns about the environmental impact of the restaurants' use "
                "of plastic straws and the high dockage fees. Some visitors also felt the place seemed elitist "
                "and not welcoming unless you have a lot of money. The outdoor seating area offers stunning "
                "views of the pier and waterfront. The menu features a range of options, including crab cakes, "
                "ahi salad, and garden burgers. The brewery offers a variety of beers, making it a popular "
                "destination for beer lovers."
            ),
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "review_info": [
                                {
                                    "review_stars": 2,
                                    "review_text": (
                                        "Please make your restaurants and drink shops go straw less. So many straws "
                                        "and you are on the ocean. Help the sea animals. The dockage fees are insane. "
                                        "The place is crawling with snobs that wont give you the time of day unless "
                                        "you have lots of money."
                                    ),
                                },
                                {
                                    "review_stars": 5,
                                    "review_text": (
                                        "Interior atmosphere is run-of-the-mill, but window tables have great views "
                                        "of the pier and waterfront. Ordered crab cakes, ahi salad, and the Garden "
                                        "Burger."
                                    ),
                                },
                                {
                                    "review_stars": 5,
                                    "review_text": "Third Window has great selection of beers and a relaxed atmosphere.",
                                },
                            ]
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    assert all(claim["verdict"] == "supported" for claim in result["claims"])
    assert all(claim["missing_facts"] == [] for claim in result["claims"])
    assert all(claim["conflicting_facts"] == [] for claim in result["claims"])


def test_semantic_mode_supports_short_structured_review_subfacts():
    result = verify_trace(
        RAGTrace(
            query="How mixed are the reviews?",
            answer=(
                "Itsuki Restaurant seems to be a mixed bag, with some customers enjoying their experience "
                "while others are disappointed. It is described as a hidden gem that provides a unique experience. "
                "According to online reviews, the food served at the restaurant is generally good, but the customer "
                "service is poor."
            ),
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "review_info": [
                                {
                                    "review_stars": 2,
                                    "review_text": "Absolutely disappointing. This experience was so disappointing.",
                                },
                                {
                                    "review_stars": 5,
                                    "review_text": "A hidden gem. You need to experience this before it is too late.",
                                },
                                {
                                    "review_stars": 1,
                                    "review_text": "Food is good but the worst service.",
                                },
                            ]
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    assert all(claim["verdict"] == "supported" for claim in result["claims"])
    assert all(claim["missing_facts"] == [] for claim in result["claims"])
    assert all(claim["conflicting_facts"] == [] for claim in result["claims"])


def test_semantic_mode_does_not_conflict_preventive_negation_paraphrases():
    result = verify_trace(
        RAGTrace(
            query="How can I prevent birds nesting on a porch and clean concrete?",
            answer=(
                "Remember to move the plastic hawk periodically to prevent the birds from becoming accustomed to it. "
                "If you have a light fixture, you can also install bird netting over it, but make sure the netting "
                "is nonflammable and safe to use around light bulbs and doesn't entangle birds. "
                "Move at an even pace and keep the nozzle at a consistent distance from the surface to avoid streaks."
            ),
            contexts=[
                TraceContext(
                    id="how_to",
                    text=(
                        "Move the plastic hawk periodically, so the birds do not become accustom to the plastic hawk. "
                        "Install bird netting over the top of the light fixture to block the birds' access to it. "
                        "Choose a netting that is nonflammable and safe to use around light bulbs. "
                        "Beware that the netting is installed so that it doesn't entangle birds. "
                        "Move at an even pace and keep the nozzle at the same distance from the surface of the concrete "
                        "at all times to ensure that no streaking occurs."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    assert all(claim["verdict"] == "supported" for claim in result["claims"])
    assert all(claim["conflicting_facts"] == [] for claim in result["claims"])


def test_semantic_mode_does_not_conflict_high_overlap_relation_paraphrases():
    result = verify_trace(
        RAGTrace(
            query="What happened?",
            answer=(
                "They are at their best when they are in control, their own boss, or working on their own. "
                "Two Delaware boys and their father are in critical condition after becoming sick, possibly from "
                "pesticide exposure, during a trip to the U.S. Virgin Islands."
            ),
            contexts=[
                TraceContext(
                    id="relations",
                    text=(
                        "You are at your best when you are in control, your own boss, or working on your own. "
                        "Two Delaware boys are in a coma and their father still is unable to talk or move two weeks "
                        "after they became sick -- perhaps from pesticide exposure -- during a trip to the U.S. "
                        "Virgin Islands."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    assert all(claim["verdict"] == "supported" for claim in result["claims"])
    assert all(claim["conflicting_facts"] == [] for claim in result["claims"])


def test_semantic_mode_neutralizes_quoted_conditional_negation():
    result = verify_trace(
        RAGTrace(
            query="How did Savannah describe the relationship?",
            answer=(
                "Savannah has been open about her feelings for Robert, saying that she wants to "
                "\"protect and love\" him and that their relationship is something she's grateful for."
            ),
            contexts=[
                TraceContext(
                    id="savannah",
                    text=(
                        "Savannah has been open about her feelings for Robert and said, "
                        "\"This is a relationship that I'm like, 'I want to protect and love and even who knows where "
                        "it's going to end up,' but even if it [didn't end] up as The One, I am so grateful to have "
                        "met him.\""
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["conflicting_facts"] == []


def test_semantic_mode_supports_critical_condition_negative_medical_paraphrases():
    result = verify_trace(
        RAGTrace(
            query="What happened to the family?",
            answer=(
                "Two Delaware boys and their father are in critical condition after becoming sick, "
                "possibly from pesticide exposure, during a trip to the U.S. Virgin Islands. "
                "The father is conscious but unable to move."
            ),
            contexts=[
                TraceContext(
                    id="medical",
                    text=(
                        "Two Delaware boys are in a coma and their father still is unable to talk or move "
                        "after they became sick, perhaps from pesticide exposure, during a trip to the U.S. "
                        "Virgin Islands. The boys are in rough shape. Esmond is conscious but cannot move."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    assert all(claim["verdict"] == "supported" for claim in result["claims"])
    assert all(claim["conflicting_facts"] == [] for claim in result["claims"])


def test_semantic_mode_supports_first_time_since_negative_paraphrase():
    result = verify_trace(
        RAGTrace(
            query="What is new about the dating situation?",
            answer=(
                "This is the first time she's been in a serious dating situation since her split "
                "from her ex-fiance Nic Kerdiles."
            ),
            contexts=[
                TraceContext(
                    id="dating",
                    text=(
                        "Seeing Savannah spending time with someone and being in a serious dating situation "
                        "hasn't happened since she was on and off with her ex-fiance, Nic Kerdiles."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["conflicting_facts"] == []


def test_semantic_mode_supports_outsourced_service_negation_context():
    result = verify_trace(
        RAGTrace(
            query="Who handled the pest control work?",
            answer=(
                "Terminix, the pest control company used by Sea Glass Vacations, is cooperating with "
                "authorities and conducting an internal investigation."
            ),
            contexts=[
                TraceContext(
                    id="provider",
                    text=(
                        "The company said it licensed an outside company, Terminix, for the pest control services. "
                        "Sea Glass Vacations does not treat the units it manages for pests but instead relies on "
                        "licensed professionals for pest control services. A spokesman for Terminix wrote that "
                        "the company is looking into this matter internally and cooperating with authorities."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["conflicting_facts"] == []


def test_semantic_mode_supports_happy_content_uncertain_relationship_paraphrase():
    result = verify_trace(
        RAGTrace(
            query="How does Savannah seem?",
            answer="While the future of their relationship remains uncertain, Savannah seems happy and content with Robert by her side.",
            contexts=[
                TraceContext(
                    id="relationship",
                    text=(
                        "Savannah Chrisley is enjoying life with a new man by her side. "
                        "Robert may be a newer man, but she is already gushing over him. "
                        "Whether this relationship lasts remains to be seen."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["conflicting_facts"] == []


def test_semantic_mode_supports_numbered_visit_call_submit_lists():
    result = verify_trace(
        RAGTrace(
            query="How do I change my postal address?",
            answer=(
                "To change your address with the U.S. Postal Service, you can visit the USPS website "
                "(moversguide.usps.com), call the USPS Call Center (1-800-ASK-USPS), or fill out and "
                "submit PS Form 3575 at any U.S. Post Office."
            ),
            contexts=[
                TraceContext(
                    id="usps",
                    text=(
                        "Postal Service Official Change of Address form online. There are three ways you can "
                        "change your address: 1.Visit https://moversguide.usps.com/. 2.Call the USPS Call Center "
                        "at 1-800-ASK-USPS. 3.Fill out and submit PS Form 3575, which you can pick up at any "
                        "U.S. Post Office."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["conflicting_facts"] == []


def test_semantic_mode_supports_optional_symptom_lists_and_answerability_boilerplate():
    result = verify_trace(
        RAGTrace(
            query="What are early pregnancy symptoms?",
            answer=(
                "The passages provide enough information to answer the question. "
                "The earliest signs and symptoms of pregnancy include mood swings, dizziness, bloating, "
                "spotting, cramping, and nausea with or without vomiting."
            ),
            contexts=[
                TraceContext(
                    id="pregnancy",
                    text=(
                        "passage 1: Mood swings are common. Dizziness can occur when blood pressure drops. "
                        "passage 2: The earliest signs of pregnancy include bloating, spotting, and cramping. "
                        "passage 3: Around half of pregnant women experience nausea and vomiting, and some "
                        "experience nausea without vomiting."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    assert all(claim["verdict"] == "supported" for claim in result["claims"])
    assert all(claim["conflicting_facts"] == [] for claim in result["claims"])


def test_semantic_mode_supports_city_itinerary_lists_with_covers_such_as():
    result = verify_trace(
        RAGTrace(
            query="What cities are on the itinerary?",
            answer=(
                "The itinerary includes visits to Hong Kong, Shenzhen, Guangzhou, Beijing, Shanghai, and "
                "the province of Jiangsu, where the Governor will engage in discussions and meetings with "
                "regional leaders, businesses, and government officials."
            ),
            contexts=[
                TraceContext(
                    id="itinerary",
                    text=(
                        "The comprehensive itinerary covers prominent cities such as Hong Kong, Shenzhen, "
                        "Guangzhou, Beijing, Shanghai, and the province of Jiangsu. In Guangdong, the Governor "
                        "will meet with regional leaders and businesses. In Beijing, discussions will involve "
                        "government officials."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["conflicting_facts"] == []


def test_semantic_mode_detects_apology_attribution_conflict():
    result = verify_trace(
        RAGTrace(
            query="Who apologized?",
            answer="The mayor of New York City, Bill de Blasio, issued an apology to the driver and passengers.",
            contexts=[
                TraceContext(
                    id="apology",
                    text=(
                        "Mayor Bill de Blasio told reporters that he had not seen the video. "
                        "Police Commissioner William Bratton issued an apology to the driver and passengers."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "contradicted"
    assert claim["conflicting_facts"]


def test_semantic_mode_detects_relative_pronoun_closed_list_conflict():
    result = verify_trace(
        RAGTrace(
            query="Which relative pronouns introduce adjective clauses?",
            answer="It is introduced by a relative pronoun (who, whose, him, her, it, that) or a subordinate conjunction.",
            contexts=[
                TraceContext(
                    id="grammar",
                    text=(
                        "It will begin with a relative pronoun (who, whose, whom, which, and that) or a "
                        "subordinate conjunction. Those are the only words that can be used to introduce "
                        "an adjective clause."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "contradicted"
    assert claim["conflicting_facts"]


def test_semantic_mode_supports_review_grounded_private_event_summary():
    result = verify_trace(
        RAGTrace(
            query="What do reviews say about Viva Modern Mexican?",
            answer=(
                "Viva Modern Mexican remains a popular spot for private events such as rehearsal dinners "
                "and welcome parties."
            ),
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "name": "Viva Modern Mexican",
                            "categories": "Breakfast & Brunch, Venues & Event Spaces, Mexican",
                            "attributes": {"OutdoorSeating": True, "WiFi": "free"},
                            "review_info": [
                                {
                                    "review_stars": 5,
                                    "review_text": (
                                        "We had our rehearsal dinner and welcome party here. The upstairs "
                                        "space was perfect and the taco buffet was delicious."
                                    ),
                                }
                            ],
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []


def test_semantic_mode_supports_review_grounded_comedy_move_summary():
    result = verify_trace(
        RAGTrace(
            query="What do reviews say about Comedy Hideaway?",
            answer=(
                "Comedy Hideaway is a recommended destination for live comedy shows, and customers mention "
                "plans to move to a bigger location in DTSB."
            ),
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "name": "Comedy Hideaway",
                            "categories": "Comedy Clubs, Venues & Event Spaces, Nightlife",
                            "attributes": {"Ambience": {"casual": True, "intimate": True}},
                            "review_info": [
                                {
                                    "review_stars": 5,
                                    "review_text": (
                                        "Great local club to see rising talent. A hidden gem. Plans are "
                                        "to move to a bigger location in DTSB."
                                    ),
                                },
                                {
                                    "review_stars": 5,
                                    "review_text": "The show was a blast, with plenty of laughs to be had.",
                                },
                            ],
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []


def test_semantic_mode_does_not_infer_absent_review_summary_details():
    result = verify_trace(
        RAGTrace(
            query="What do reviews say about Comedy Hideaway?",
            answer="Customers mention plans to move to a bigger location in DTSB.",
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "name": "Comedy Hideaway",
                            "categories": "Comedy Clubs, Venues & Event Spaces, Nightlife",
                            "review_info": [
                                {
                                    "review_stars": 5,
                                    "review_text": "The show was a blast, with plenty of laughs to be had.",
                                }
                            ],
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] != "supported"
    assert claim["missing_facts"]


def test_semantic_mode_supports_review_positive_negative_experience_summary():
    result = verify_trace(
        RAGTrace(
            query="What do reviews say about Epic Bowl?",
            answer=(
                "Another customer had a positive experience during their visit. On the other hand, a "
                "different customer had a negative experience and had trouble accessing the business because "
                "it was consistently closed."
            ),
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "name": "Epic Bowl",
                            "categories": "Specialty Food, Breakfast & Brunch, Juice Bars & Smoothies",
                            "review_info": [
                                {
                                    "review_stars": 5,
                                    "review_text": "I was visiting Santa Barbara and the staff were helpful. The visit was amazing.",
                                },
                                {
                                    "review_stars": 1,
                                    "review_text": "I tried to go five times and it is always closed.",
                                },
                            ],
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    assert all(claim["verdict"] == "supported" for claim in result["claims"])
    assert all(claim["missing_facts"] == [] for claim in result["claims"])


def test_semantic_mode_supports_review_affordable_comedy_summary():
    result = verify_trace(
        RAGTrace(
            query="What do reviews say about Comedy Hideaway?",
            answer="Comedy Hideaway is a good spot for a laughter-filled evening without breaking the bank.",
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "name": "Comedy Hideaway",
                            "categories": "Comedy Clubs, Arts & Entertainment",
                            "review_info": [
                                {
                                    "review_stars": 5,
                                    "review_text": "The comics are good, drinks are cheap, and plenty of laughs can be had.",
                                }
                            ],
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["missing_facts"] == []


def test_semantic_mode_does_not_infer_slow_service_from_positive_staff_reviews():
    result = verify_trace(
        RAGTrace(
            query="What do reviews say about the brewery?",
            answer="Customers appreciate the knowledgeable staff, but the service can sometimes be slow.",
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "name": "Modern Times Academy",
                            "categories": "Beer Bar, Vegan, Restaurants",
                            "review_info": [
                                {
                                    "review_stars": 5,
                                    "review_text": (
                                        "The staff is very friendly and knowledgeable about beers. "
                                        "The food is delicious, the patio is great, and I can't wait to return."
                                    ),
                                }
                            ],
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] != "supported"
    assert claim["missing_facts"]


def test_semantic_mode_does_not_conflict_generic_casual_restaurant_with_ambience_false():
    result = verify_trace(
        RAGTrace(
            query="What is Sandpiper Grill like?",
            answer="Sandpiper Grill seems to be a casual restaurant serving sandwiches and salads.",
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "name": "Sandpiper Grill",
                            "categories": "American (Traditional), Sandwiches, Restaurants",
                            "attributes": {"Ambience": {"casual": False}},
                            "review_info": [
                                {
                                    "review_stars": 5,
                                    "review_text": "The sandwich and salads are fresh and tasty.",
                                }
                            ],
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] != "contradicted"
    assert claim["conflicting_facts"] == []


def test_semantic_mode_uses_structured_json_attributes_for_conflict():
    result = verify_trace(
        RAGTrace(
            query="What amenities does the bar offer?",
            answer="The bar offers Wi-Fi and validated parking options.",
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "attributes": {
                                "BusinessParking": {"street": True, "validated": False},
                                "WiFi": "no",
                            },
                            "categories": "Dive Bars, Bars",
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "contradicted"
    assert set(claim["conflicting_facts"]) == {"wifi", "validated parking"}
    assert "contradicted_answer" in result["summary"]["failure_types"]


def test_semantic_mode_does_not_let_json_false_values_contradict_supported_field():
    result = verify_trace(
        RAGTrace(
            query="What parking does the bar offer?",
            answer="The bar offers street parking.",
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "attributes": {
                                "BusinessParking": {
                                    "garage": False,
                                    "lot": False,
                                    "street": True,
                                    "validated": False,
                                },
                                "WiFi": "no",
                            },
                            "categories": "Dive Bars, Bars",
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["conflicting_facts"] == []


def test_semantic_mode_does_not_conflict_specific_negated_parking_options():
    result = verify_trace(
        RAGTrace(
            query="What parking is available?",
            answer="Street parking is available, but there is no garage, validated parking, lot, or valet service.",
            contexts=[
                TraceContext(
                    id="yelp_structured",
                    text=json.dumps(
                        {
                            "attributes": {
                                "BusinessParking": {
                                    "garage": False,
                                    "lot": False,
                                    "street": True,
                                    "valet": False,
                                    "validated": False,
                                }
                            }
                        }
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "supported"
    assert claim["conflicting_facts"] == []


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


def test_led_by_conflict_is_not_supported_by_shared_player_stats():
    result = verify_trace(
        RAGTrace(
            query="Who led Duke?",
            answer="Duke won against Michigan State 81-61, led by Jahlil Okafor's 18 points and 10 rebounds.",
            contexts=[
                TraceContext(
                    id="final_four",
                    text=(
                        "Freshman Justise Winslow led Duke with 19 points while national freshman "
                        "of the year Jahlil Okafor had 18 points, 10 of which came in the first half."
                    ),
                )
            ],
        ),
        mode="semantic",
    )

    claim = result["claims"][0]
    assert claim["verdict"] == "contradicted"
    assert claim["conflicting_fact_details"][0]["type"] == "relation"
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
