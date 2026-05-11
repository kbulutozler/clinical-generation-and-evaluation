#!/usr/bin/env python3
"""Smoke-check the three local vLLM OpenAI-compatible servers."""

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request


DEFAULT_SERVERS = {
    "generation": ("http://127.0.0.1:8010/v1", "Qwen/Qwen3.5-2B"),
    "evaluator": ("http://127.0.0.1:8011/v1", "google/gemma-4-E4B-it"),
    "reflector": ("http://127.0.0.1:8012/v1", "google/gemma-4-26B-A4B-it"),
}


def request_json(url: str, payload: dict | None = None, timeout: int = 30) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", "Bearer EMPTY")
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def check_models(base_url: str, expected_model: str) -> bool:
    try:
        payload = request_json(f"{base_url.rstrip('/')}/models", timeout=10)
    except (OSError, urllib.error.URLError, TimeoutError):
        return False
    model_ids = {item.get("id") for item in payload.get("data", [])}
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout-seconds", type=int, default=900)
    parser.add_argument("--skip-chat", action="store_true")
    parser.add_argument("--generation-url", default=DEFAULT_SERVERS["generation"][0])
    parser.add_argument("--evaluator-url", default=DEFAULT_SERVERS["evaluator"][0])
    parser.add_argument("--reflector-url", default=DEFAULT_SERVERS["reflector"][0])
    parser.add_argument("--generation-model", default=DEFAULT_SERVERS["generation"][1])
    parser.add_argument("--evaluator-model", default=DEFAULT_SERVERS["evaluator"][1])
    parser.add_argument("--reflector-model", default=DEFAULT_SERVERS["reflector"][1])
    args = parser.parse_args()

    servers = {
        "generation": (args.generation_url, args.generation_model),
        "evaluator": (args.evaluator_url, args.evaluator_model),
        "reflector": (args.reflector_url, args.reflector_model),
    }
    deadline = time.time() + args.timeout_seconds
    ready: set[str] = set()

    while time.time() < deadline and len(ready) < len(servers):
        for role, (base_url, model) in servers.items():
            if role in ready:
                continue
            if check_models(base_url, model):
                print(f"{role}: model endpoint ready at {base_url} ({model})")
                ready.add(role)
        if len(ready) < len(servers):
            time.sleep(10)

    missing = sorted(set(servers) - ready)
    if missing:
        raise SystemExit(f"Timed out waiting for servers: {', '.join(missing)}")

    if args.skip_chat:
        print("3")
        return

    chat_ok = 0
    for role, (base_url, model) in servers.items():
        if check_chat(base_url, model):
            print(f"{role}: chat completion OK")
            chat_ok += 1
        else:
            raise SystemExit(f"{role}: chat completion failed")

    print(chat_ok)


if __name__ == "__main__":
    main()
