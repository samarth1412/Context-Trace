from contexttrace.verify.schema import TraceContext
from contexttrace.verify.spans import split_context_spans


def test_sentence_spans_are_minimal_and_preserve_offsets():
    context = TraceContext(id="ctx", text="Alpha is supported. Beta is contradicted.", metadata={})
    spans = split_context_spans(context)

    assert [span.text for span in spans] == ["Alpha is supported.", "Beta is contradicted."]
    assert [(span.start_char, span.end_char) for span in spans] == [(0, 19), (20, 41)]


def test_passage_context_exposes_block_and_sentence_spans_for_multispan_support():
    context = TraceContext(id="ctx", text="Passage 1: Alpha is supported. Beta is supported.", metadata={})
    texts = [span.text for span in split_context_spans(context)]

    assert "Alpha is supported." in texts
    assert "Beta is supported." in texts
