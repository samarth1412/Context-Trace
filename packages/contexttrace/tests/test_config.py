from pathlib import Path

from contexttrace.config import load_config


ENV_KEYS = (
    "CONTEXTTRACE_API_KEY",
    "CONTEXTTRACE_PROJECT",
    "CONTEXTTRACE_BASE_URL",
    "CONTEXTTRACE_API_URL",
    "CONTEXTTRACE_MODE",
    "CONTEXTTRACE_TIMEOUT",
    "CONTEXTTRACE_RETRIES",
    "CONTEXTTRACE_DEBUG",
    "CONTEXTTRACE_LOCAL_STORE_DIR",
    "CONTEXTTRACE_STORAGE_PATH",
    "CONTEXTTRACE_LOCAL_ONLY",
    "CONTEXTTRACE_LOG_CHUNK_TEXT",
    "CONTEXTTRACE_LOG_ANSWER_TEXT",
    "CONTEXTTRACE_JUDGE_PROVIDER",
    "CONTEXTTRACE_JUDGE_BASE_URL",
    "CONTEXTTRACE_JUDGE_API_KEY",
    "CONTEXTTRACE_JUDGE_MODEL",
    "CONTEXTTRACE_JUDGE_CACHE",
    "CONTEXTTRACE_JUDGE_CACHE_PATH",
    "CONTEXTTRACE_EVAL_ENDPOINT",
)


def test_config_loads_file_env_and_direct_precedence(monkeypatch, tmp_path):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    config_path = tmp_path / "contexttrace.yaml"
    config_path.write_text(
        "\n".join(
            [
                "api_key: file_key",
                "project: file-project",
                "base_url: http://file-api",
                "mode: hosted",
                "timeout: 15",
                "retries: 1",
                "debug: false",
                "local_store_dir: file-store",
                "storage_path: file-store/contexttrace.db",
                "local_only: true",
                "log_chunk_text: false",
                "log_answer_text: true",
                "judge_provider: local",
                "judge_base_url: http://file-judge/v1",
                "judge_api_key: file_judge_key",
                "judge_model: file-judge-model",
                "judge_cache_enabled: false",
                "judge_cache_path: file-store/judge_cache.json",
                "eval_endpoint: http://file-rag/query",
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("CONTEXTTRACE_PROJECT", "env-project")
    monkeypatch.setenv("CONTEXTTRACE_BASE_URL", "http://env-api")
    monkeypatch.setenv("CONTEXTTRACE_DEBUG", "true")

    config = load_config(
        config_path=str(config_path),
        api_key="direct_key",
        project="direct-project",
        mode="local",
    )

    assert config.api_key == "direct_key"
    assert config.project == "direct-project"
    assert config.base_url == "http://env-api"
    assert config.mode == "local"
    assert config.timeout == 15
    assert config.retries == 1
    assert config.debug is True
    assert config.local_store_dir == "file-store"
    assert config.storage_path == "file-store/contexttrace.db"
    assert config.local_only is True
    assert config.log_chunk_text is False
    assert config.log_answer_text is True
    assert config.judge_provider == "local"
    assert config.judge_base_url == "http://file-judge/v1"
    assert config.judge_api_key == "file_judge_key"
    assert config.judge_model == "file-judge-model"
    assert config.judge_cache_enabled is False
    assert config.judge_cache_path == "file-store/judge_cache.json"
    assert config.eval_endpoint == "http://file-rag/query"


def test_config_defaults_to_local_sqlite(monkeypatch):
    for key in ENV_KEYS:
        monkeypatch.delenv(key, raising=False)

    config = load_config(project="local-project")

    assert config.mode == "local"
    assert config.local_only is True
    assert Path(config.storage_path) == Path(".contexttrace/contexttrace.db")
    assert config.judge_provider == "local"
    assert config.judge_base_url == ""
    assert config.judge_api_key is None
    assert config.judge_model == ""
    assert config.judge_cache_enabled is True
    assert config.judge_cache_path == ".contexttrace/judge_cache.json"
