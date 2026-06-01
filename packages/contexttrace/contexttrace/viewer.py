from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any, Callable
from wsgiref.simple_server import make_server

from contexttrace.report import ReportGenerator
from contexttrace.storage import SQLiteTraceStore


def create_viewer_app(storage_path: str = ".contexttrace/contexttrace.db") -> Callable:
    store = SQLiteTraceStore(storage_path)

    def app(environ: dict[str, Any], start_response: Callable) -> list[bytes]:
        path = environ.get("PATH_INFO") or "/"
        try:
            status = "200 OK"
            body = _route(path, store)
        except Exception as exc:
            status = "500 Internal Server Error"
            body = _page("ContextTrace Viewer Error", "<p>%s</p>" % escape(str(exc)))
        start_response(status, [("Content-Type", "text/html; charset=utf-8")])
        return [body.encode("utf-8")]

    return app


def serve_viewer(
    *,
    storage_path: str = ".contexttrace/contexttrace.db",
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    app = create_viewer_app(storage_path)
    with make_server(host, port, app) as server:
        print("ContextTrace local viewer: http://%s:%s" % (host, port))
        server.serve_forever()


def _route(path: str, store: SQLiteTraceStore) -> str:
    if path == "/":
        status = store.trace_count()
        last_eval = store.last_eval_run()
        return _page(
            "ContextTrace Local Viewer",
            """
            <section class="hero">
              <h1>ContextTrace Local Viewer</h1>
              <p>Inspect local RAG and agent traces stored in SQLite.</p>
              <div class="metrics">
                <div><dt>Traces</dt><dd>{trace_count}</dd></div>
                <div><dt>Last Eval Run</dt><dd>{last_eval}</dd></div>
              </div>
            </section>
            """.format(
                trace_count=status,
                last_eval=escape(str((last_eval or {}).get("id") or "None")),
            ),
        )
    if path == "/traces":
        rows = []
        for trace in store.list_traces(limit=100):
            failure = ((trace.get("evaluation") or {}).get("failure") or {}).get("failure_type") or "not_evaluated"
            score = ((trace.get("evaluation") or {}).get("scores") or {}).get("citation_support", "")
            rows.append(
                "<tr><td><a href=\"/traces/{id}\">{id}</a></td><td>{query}</td><td>{failure}</td><td>{score}</td><td>{created}</td></tr>".format(
                    id=escape(str(trace.get("id"))),
                    query=escape(str(trace.get("query") or "")[:140]),
                    failure=escape(str(failure)),
                    score=escape(str(score)),
                    created=escape(str(trace.get("created_at") or "")),
                )
            )
        return _page(
            "Traces",
            "<h1>Traces</h1><table><thead><tr><th>Trace ID</th><th>Query</th><th>Failure</th><th>Citation Support</th><th>Created</th></tr></thead><tbody>%s</tbody></table>"
            % ("\n".join(rows) or "<tr><td colspan=\"5\">No traces found.</td></tr>"),
        )
    if path.startswith("/traces/"):
        trace_id = path.rsplit("/", 1)[-1]
        trace = store.get_trace(trace_id)
        return ReportGenerator().render(trace)
    if path == "/eval-runs":
        rows = []
        for run in store.list_eval_runs(limit=100):
            summary = run.get("summary") or {}
            rows.append(
                "<tr><td>{id}</td><td>{dataset}</td><td>{endpoint}</td><td>{score}</td><td>{created}</td></tr>".format(
                    id=escape(str(run.get("id"))),
                    dataset=escape(str(run.get("dataset") or "")),
                    endpoint=escape(str(run.get("endpoint") or "")),
                    score=escape(str(summary.get("reliability_score", ""))),
                    created=escape(str(run.get("created_at") or "")),
                )
            )
        return _page(
            "Eval Runs",
            "<h1>Eval Runs</h1><table><thead><tr><th>ID</th><th>Dataset</th><th>Endpoint</th><th>Reliability</th><th>Created</th></tr></thead><tbody>%s</tbody></table>"
            % ("\n".join(rows) or "<tr><td colspan=\"5\">No eval runs found.</td></tr>"),
        )
    if path == "/reports":
        report_dir = Path(".contexttrace") / "reports"
        items = []
        for report in sorted(report_dir.glob("*.html")) if report_dir.exists() else []:
            items.append("<li>%s</li>" % escape(str(report)))
        return _page("Reports", "<h1>Reports</h1><ul>%s</ul>" % ("\n".join(items) or "<li>No reports found.</li>"))
    return _page("Not Found", "<h1>Not Found</h1><p>No local viewer page exists for this path.</p>")


def _page(title: str, body: str) -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{ --bg: #f7f8fa; --panel: #fff; --text: #1f2933; --muted: #697386; --line: #d8dee8; --accent: #2458d3; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; background: var(--bg); color: var(--text); font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width: 1120px; margin: 0 auto; padding: 32px 20px 56px; }}
    nav {{ display: flex; gap: 16px; margin-bottom: 22px; }}
    nav a {{ color: var(--accent); text-decoration: none; font-weight: 700; }}
    h1 {{ margin-top: 0; }}
    section, table {{ background: var(--panel); border: 1px solid var(--line); border-radius: 8px; }}
    section {{ padding: 20px; }}
    table {{ width: 100%; border-collapse: collapse; overflow: hidden; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px; text-align: left; vertical-align: top; }}
    th {{ color: var(--muted); font-size: 12px; text-transform: uppercase; }}
    .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 16px; }}
    .metrics div {{ border: 1px solid var(--line); border-radius: 8px; padding: 12px; background: #fbfcfe; }}
    dt {{ color: var(--muted); font-size: 12px; font-weight: 700; text-transform: uppercase; }}
    dd {{ margin: 4px 0 0; font-size: 20px; }}
  </style>
</head>
<body>
  <main>
    <nav>
      <a href="/">Overview</a>
      <a href="/traces">Traces</a>
      <a href="/eval-runs">Eval Runs</a>
      <a href="/reports">Reports</a>
    </nav>
    {body}
  </main>
</body>
</html>""".format(title=escape(title), body=body)
