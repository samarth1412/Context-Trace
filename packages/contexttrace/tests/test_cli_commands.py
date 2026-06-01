from contexttrace import ContextTrace
from contexttrace import __version__
from contexttrace.cli import main


def test_cli_version(capsys):
    assert main(["--version"]) == 0

    assert __version__ in capsys.readouterr().out


def test_cli_init_config_trace_list_and_report(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == 0
    init_output = capsys.readouterr().out
    assert "contexttrace.yaml" in init_output
    assert (tmp_path / "contexttrace.yaml").exists()
    assert (tmp_path / ".contexttrace" / "contexttrace.db").exists()
    assert (tmp_path / "evals" / "sample_questions.json").exists()

    ct = ContextTrace(config_path="contexttrace.yaml")
    with ct.trace(query="What is the refund policy?") as trace:
        trace.log_retrieval(
            [{"chunk_id": "chunk_1", "content": "Refunds are available within 30 days."}]
        )
        trace.log_context(chunk_ids=["chunk_1"])
        trace.log_answer("Refunds are available within 30 days.")
        trace.log_citations(
            [{"claim": "Refunds are available within 30 days.", "source_chunk_id": "chunk_1"}]
        )
        trace.evaluate()

    assert main(["config", "show"]) == 0
    config_output = capsys.readouterr().out
    assert '"mode": "local"' in config_output

    assert main(["trace", "list"]) == 0
    list_output = capsys.readouterr().out
    assert trace.trace_id in list_output
    assert "What is the refund policy?" in list_output

    report_path = tmp_path / "last-report.html"
    assert main(["report", "--last", "--output", str(report_path)]) == 0
    report_output = capsys.readouterr().out
    assert str(report_path) in report_output
    assert report_path.exists()
    assert "ContextTrace Report" in report_path.read_text(encoding="utf-8")

    opened = []
    monkeypatch.setattr("contexttrace.cli.webbrowser.open", lambda value: opened.append(value))
    assert main(["report", "--last", "--output", str(tmp_path / "open-report.html"), "--open"]) == 0
    assert opened

    assert main(["status"]) == 0
    assert "Trace count: 1" in capsys.readouterr().out

    assert main(["traces", "show", trace.trace_id]) == 0
    assert "Failure type:" in capsys.readouterr().out

    assert main(["doctor"]) == 0
    assert "SQLite writable" in capsys.readouterr().out


def test_cli_demo_creates_trace_and_report(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)

    assert main(["init"]) == 0
    capsys.readouterr()
    assert main(["demo", "--dataset", "refund_policy"]) == 0
    output = capsys.readouterr().out

    assert "Created demo trace:" in output
    assert list((tmp_path / ".contexttrace" / "reports").glob("*.html"))
