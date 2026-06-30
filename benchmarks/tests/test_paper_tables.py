from pathlib import Path
import json

from paper.generate_tables import generate_paper_tables


def test_paper_table_generation_is_complete_and_claim_safe(tmp_path):
    outputs = generate_paper_tables(
        tex_dir=tmp_path / "tex",
        markdown_dir=tmp_path / "markdown",
    )

    assert len(outputs) == 12
    assert all(Path(path).is_file() for path in outputs.values())
    markdown = {
        path.name: path.read_text(encoding="utf-8")
        for path in (tmp_path / "markdown").glob("*.md")
    }
    assert "assisted_review_pending_independent" in markdown["table1_main_results.md"]
    assert "same-ID cached baseline" in markdown["table2_baselines.md"]
    assert "not_available" in markdown["table3_ablations.md"]
    assert "pending three independent reviewers" in markdown["table4_rq4_actionability.md"]
    assert "not_measured" in markdown["table5_error_analysis.md"]
    assert "pending review" in markdown["table6_reproducibility.md"]
    assert all("review status" in content.lower() for content in markdown.values())


def test_generated_latex_tables_escape_review_statuses(tmp_path):
    generate_paper_tables(tex_dir=tmp_path / "tex", markdown_dir=tmp_path / "markdown")

    main = (tmp_path / "tex" / "table1_main_results.tex").read_text(encoding="utf-8")
    rq4 = (tmp_path / "tex" / "table4_rq4_actionability.tex").read_text(encoding="utf-8")

    assert "assisted\\_review\\_pending\\_independent" in main
    assert "N/A" in rq4
    assert "\\begin{table*}" in main


def test_paper_table_generation_keeps_simulated_rq4_separate(tmp_path):
    rq4 = tmp_path / "rq4.json"
    rq4.write_text(
        json.dumps(
            {
                "pilot_type": "controlled_llm_simulated_actionability_not_human_validation",
                "case_count": 40,
                "simulated_reviewer_agents": 3,
                "settings": {
                    setting: {
                        "root_cause_accuracy": 0.1,
                        "fix_correctness_proxy": 0.2,
                        "actionability_score": 3.0,
                        "dangerous_false_green_rate": 0.4,
                    }
                    for setting in ("raw_trace", "score_only", "contexttrace")
                },
            }
        ),
        encoding="utf-8",
    )

    generate_paper_tables(
        tex_dir=tmp_path / "tex",
        markdown_dir=tmp_path / "markdown",
        rq4_results_path=rq4,
    )
    table = (tmp_path / "markdown" / "table4_rq4_actionability.md").read_text(encoding="utf-8")

    assert "pending three independent reviewers" in table
    assert "LLM-simulated pilot; not human validation" in table
    assert "Simulated C: evidence chain" in table
