#!/usr/bin/env python3
"""Smoke-check local vLLM OpenAI-compatible servers.

Reads ``models`` and ``endpoints`` strictly from ``gepa/config.yaml`` (no hardcoded
URL/model fallbacks). Install PyYAML (e.g. ``uv run --with pyyaml python3 …``).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROLES_ORDER = ("generation", "evaluator", "reflector")


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def load_gepa_server_defaults(path: Path) -> dict[str, str]:
    """Load URLs and model ids from GEPA YAML; exit on missing file, PyYAML, or keys."""
    if not path.is_file():
        raise SystemExit(f"GEPA config must be an existing file: {path}")
    try:
        import yaml
    except ImportError as exc:
        raise SystemExit(
            "PyYAML is required for check_vllm_servers.py. Example:\n"
            "  uv run --python 3.12 --with pyyaml -- python3 gepa/servers/check_vllm_servers.py"
        ) from exc
    try:
        raw = path.read_text()
    except OSError as exc:
        raise SystemExit(f"Cannot read GEPA config {path}: {exc}") from exc
    try:
        cfg = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise SystemExit(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(cfg, dict):
        raise SystemExit(f"GEPA config must be a YAML mapping: {path}")
    models = cfg.get("models")
    ep = cfg.get("endpoints")
    if not isinstance(models, dict):
        raise SystemExit(f"GEPA config {path}: missing or invalid [models] section.")
    if not isinstance(ep, dict):
        raise SystemExit(f"GEPA config {path}: missing or invalid [endpoints] section.")
    out: dict[str, str] = {}
    for mk in ("generation_model", "evaluator_model", "reflector_model"):
        v = models.get(mk)
        if v is None or not str(v).strip():
            raise SystemExit(f"GEPA config {path}: missing or empty models.{mk}")
        out[mk] = str(v).strip()
    for ek in ("generation_url", "evaluator_url", "reflector_url"):
        v = ep.get(ek)
        if v is None or not str(v).strip():
            raise SystemExit(f"GEPA config {path}: missing or empty endpoints.{ek}")
        out[ek] = str(v).strip()
    return out


def request_json(url: str, payload: dict | None = None, timeout: int = 30) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer EMPTY")
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_model_ids(base_url: str) -> tuple[set[str] | None, str | None]:
    """Return (model_ids, error_message). model_ids is None if the request failed."""
    try:
        payload = request_json(f"{base_url.rstrip('/')}/models", timeout=10)
    except (OSError, urllib.error.URLError, TimeoutError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    model_ids = {item.get("id") for item in payload.get("data", []) if isinstance(item, dict)}
    return model_ids, None


def check_models(base_url: str, expected_model: str) -> bool:
    model_ids, _ = fetch_model_ids(base_url)
    if model_ids is None:
        return False
    return expected_model in model_ids


def check_chat(base_url: str, model: str) -> bool:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with the single word ready."}],
        "max_tokens": 8,
        "temperature": 0.0,
    }
    try:
        response = request_json(f"{base_url.rstrip('/')}/chat/completions", payload=payload)
    except (OSError, urllib.error.URLError, TimeoutError):
        return False
    content = response["choices"][0]["message"].get("content") or ""
    return bool(content.strip())


def _role_servers(args: argparse.Namespace) -> dict[str, tuple[str, str]]:
    return {
        "generation": (args.generation_url, args.generation_model),
        "evaluator": (args.evaluator_url, args.evaluator_model),
        "reflector": (args.reflector_url, args.reflector_model),
    }


def _unique_probe_targets(servers: dict[str, tuple[str, str]]) -> list[tuple[str, str, frozenset[str]]]:
    """Merge roles that share the same OpenAI base URL and model id."""
    buckets: dict[tuple[str, str], set[str]] = {}
    for role in ROLES_ORDER:
        if role not in servers:
            continue
        url, model = servers[role]
        key = (url.rstrip("/"), model)
        buckets.setdefault(key, set()).add(role)
    return [(url, model, frozenset(roles)) for (url, model), roles in buckets.items()]


def main() -> None:
    bootstrap = argparse.ArgumentParser(add_help=False)
    bootstrap.add_argument(
        "--gepa-config",
        default=str(_repo_root() / "gepa" / "config.yaml"),
        help="Path to gepa/config.yaml (must contain models.* and endpoints.*).",
    )
    b_args, _ = bootstrap.parse_known_args()
    gepa_path = Path(b_args.gepa_config).expanduser().resolve()
    d = load_gepa_server_defaults(gepa_path)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gepa-config", default=str(gepa_path))
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--skip-chat", action="store_true")
    parser.add_argument("--generation-url", default=d["generation_url"])
    parser.add_argument("--evaluator-url", default=d["evaluator_url"])
    parser.add_argument("--reflector-url", default=d["reflector_url"])
    parser.add_argument("--generation-model", default=d["generation_model"])
    parser.add_argument("--evaluator-model", default=d["evaluator_model"])
    parser.add_argument("--reflector-model", default=d["reflector_model"])
    args = parser.parse_args()

    servers = _role_servers(args)
    all_roles = set(servers)
    probes = _unique_probe_targets(servers)
    deadline = time.time() + args.timeout_seconds
    ready: set[str] = set()
    started = time.time()

    while time.time() < deadline and len(ready) < len(all_roles):
        for base_url, model, roles in probes:
            if roles <= ready:
                continue
            model_ids, err = fetch_model_ids(base_url)
            if model_ids is None:
                continue
            if model not in model_ids:
                ids_preview = sorted(m for m in model_ids if m)[:20]
                print(
                    f"error: {base_url} is up but expected model id {model!r} is missing from /models.",
                    file=sys.stderr,
                )
                print(f"  roles still waiting: {', '.join(sorted(roles - ready))}", file=sys.stderr)
                print(f"  served ids (sample): {ids_preview}", file=sys.stderr)
                raise SystemExit(2)
            for role in roles:
                print(f"{role}: model endpoint ready at {base_url} ({model})")
                ready.add(role)
        if len(ready) < len(all_roles):
            elapsed = time.time() - started
            time.sleep(2.0 if elapsed < 90 else 10.0)

    missing = sorted(all_roles - ready)
    if missing:
        print("Timed out waiting for servers: " + ", ".join(missing), file=sys.stderr)
        for role in missing:
            url, model = servers[role]
            model_ids, err = fetch_model_ids(url)
            print(f"  [{role}] url={url} expected_model={model!r}", file=sys.stderr)
            if err:
                print(f"    /models: {err}", file=sys.stderr)
            elif model_ids is not None:
                preview = sorted(m for m in model_ids if m)[:30]
                print(f"    /models returned {len(model_ids)} id(s), sample={preview}", file=sys.stderr)
        raise SystemExit(1)

    if args.skip_chat:
        print(len(all_roles))
        return

    chat_ok = 0
    for role in ROLES_ORDER:
        if role not in servers:
            continue
        base_url, model = servers[role]
        if check_chat(base_url, model):
            print(f"{role}: chat completion OK")
            chat_ok += 1
        else:
            raise SystemExit(f"{role}: chat completion failed")

    print(chat_ok)


if __name__ == "__main__":
    main()
