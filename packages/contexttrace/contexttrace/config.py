from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from contexttrace.errors import ContextTraceConfigError


DEFAULT_PROJECT = "default"
DEFAULT_BASE_URL = "http://localhost:8000"
DEFAULT_MODE = "local"
DEFAULT_LOCAL_STORE_DIR = ".contexttrace"
DEFAULT_STORAGE_PATH = ".contexttrace/contexttrace.db"
CONFIG_FILE = "contexttrace.yaml"


@dataclass(frozen=True)
class ContextTraceConfig:
    api_key: Optional[str] = None
    project: str = DEFAULT_PROJECT
    base_url: str = DEFAULT_BASE_URL
    mode: str = DEFAULT_MODE
    local_only: bool = True
    timeout: float = 30.0
    retries: int = 2
    debug: bool = False
    local_store_dir: str = DEFAULT_LOCAL_STORE_DIR
    storage_path: str = DEFAULT_STORAGE_PATH
    log_chunk_text: bool = True
    log_answer_text: bool = True
    eval_endpoint: Optional[str] = None
    judge_provider: str = "local"


def load_config(
    *,
    api_key: Optional[str] = None,
    project: Optional[str] = None,
    base_url: Optional[str] = None,
    api_url: Optional[str] = None,
    mode: Optional[str] = None,
    local_only: Optional[bool] = None,
    timeout: Optional[float] = None,
    retries: Optional[int] = None,
    debug: Optional[bool] = None,
    local_store_dir: Optional[str] = None,
    storage_path: Optional[str] = None,
    log_chunk_text: Optional[bool] = None,
    log_answer_text: Optional[bool] = None,
    eval_endpoint: Optional[str] = None,
    judge_provider: Optional[str] = None,
    config_path: Optional[str] = None,
) -> ContextTraceConfig:
    file_values = _read_config_file(config_path)
    env_base_url = os.getenv("CONTEXTTRACE_API_URL") or os.getenv("CONTEXTTRACE_BASE_URL")
    explicit_api_url = api_url or base_url
    resolved_mode = _first(
        mode,
        os.getenv("CONTEXTTRACE_MODE"),
        file_values.get("mode"),
        "hosted" if explicit_api_url and local_only is not True else None,
        "hosted" if env_base_url and local_only is not True else None,
        DEFAULT_MODE,
    )
    resolved_local_store_dir = str(
        _first(
            local_store_dir,
            os.getenv("CONTEXTTRACE_LOCAL_STORE_DIR"),
            file_values.get("local_store_dir"),
            DEFAULT_LOCAL_STORE_DIR,
        )
    )
    resolved_storage_path = str(
        _first(
            storage_path,
            os.getenv("CONTEXTTRACE_STORAGE_PATH"),
            file_values.get("storage_path"),
            str(Path(resolved_local_store_dir) / "contexttrace.db"),
        )
    )
    resolved_local_only = _as_bool(
        _first(
            local_only,
            os.getenv("CONTEXTTRACE_LOCAL_ONLY"),
            file_values.get("local_only"),
            False if resolved_mode == "hosted" else True,
        )
    )

    resolved = ContextTraceConfig(
        api_key=_first(
            api_key,
            os.getenv("CONTEXTTRACE_API_KEY"),
            file_values.get("api_key"),
        ),
        project=str(
            _first(
                project,
                os.getenv("CONTEXTTRACE_PROJECT"),
                file_values.get("project"),
                DEFAULT_PROJECT,
            )
        ),
        base_url=str(
            _first(
                api_url,
                base_url,
                env_base_url,
                file_values.get("base_url"),
                file_values.get("api_url"),
                DEFAULT_BASE_URL,
            )
        ),
        mode=str(resolved_mode),
        local_only=resolved_local_only,
        timeout=float(
            _first(
                timeout,
                os.getenv("CONTEXTTRACE_TIMEOUT"),
                file_values.get("timeout"),
                30.0,
            )
        ),
        retries=int(
            _first(
                retries,
                os.getenv("CONTEXTTRACE_RETRIES"),
                file_values.get("retries"),
                2,
            )
        ),
        debug=_as_bool(
            _first(
                debug,
                os.getenv("CONTEXTTRACE_DEBUG"),
                file_values.get("debug"),
                False,
            )
        ),
        local_store_dir=resolved_local_store_dir,
        storage_path=resolved_storage_path,
        log_chunk_text=_as_bool(
            _first(
                log_chunk_text,
                os.getenv("CONTEXTTRACE_LOG_CHUNK_TEXT"),
                file_values.get("log_chunk_text"),
                True,
            )
        ),
        log_answer_text=_as_bool(
            _first(
                log_answer_text,
                os.getenv("CONTEXTTRACE_LOG_ANSWER_TEXT"),
                file_values.get("log_answer_text"),
                True,
            )
        ),
        eval_endpoint=_first(
            eval_endpoint,
            os.getenv("CONTEXTTRACE_EVAL_ENDPOINT"),
            file_values.get("eval_endpoint"),
        ),
        judge_provider=str(
            _first(
                judge_provider,
                os.getenv("CONTEXTTRACE_JUDGE_PROVIDER"),
                file_values.get("judge_provider"),
                "local",
            )
        ),
    )

    if resolved.mode not in {"hosted", "local"}:
        raise ContextTraceConfigError("ContextTrace mode must be 'hosted' or 'local'.")
    return resolved


def write_default_config(path: str = CONFIG_FILE, *, overwrite: bool = False) -> str:
    output = Path(path)
    if output.exists() and not overwrite:
        return str(output)
    output.write_text(
        "\n".join(
            [
                "mode: local",
                "project: default",
                "local_only: true",
                "local_store_dir: .contexttrace",
                "storage_path: .contexttrace/contexttrace.db",
                "log_chunk_text: true",
                "log_answer_text: true",
                "judge_provider: local",
                "api_key: ''",
                "base_url: ''",
                "timeout: 30",
                "retries: 2",
                "debug: false",
                "eval_endpoint: ''",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return str(output)


def _read_config_file(config_path: Optional[str]) -> dict[str, Any]:
    candidates = [Path(config_path)] if config_path else [Path(CONFIG_FILE)]
    for candidate in candidates:
        if candidate.exists():
            return _parse_simple_yaml(candidate.read_text(encoding="utf-8"))
    return {}


def _parse_simple_yaml(text: str) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, value = line.split(":", 1)
        parsed = value.strip().strip("\"'")
        if parsed == "":
            values[key.strip()] = None
        elif parsed.lower() in {"true", "false"}:
            values[key.strip()] = parsed.lower() == "true"
        else:
            values[key.strip()] = parsed
    return values


def _first(*values: Any) -> Any:
    for value in values:
        if value is not None:
            return value
    return None


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}
