"""Ollama wrapper with an on-disk cache.

Every call (query rewrites, HyDE passages, answers, judge verdicts) goes
through generate(), keyed by model + system prompt + prompt + options. On a
CPU a 3B model takes seconds per call, so re-running an evaluation should
never repeat one: with temperature 0 the cached answer is the answer.
"""
import hashlib
import json
import os
import time

import config


def cache_key(prompt, system=None, model=None, options=None):
    payload = {
        "model": model or config.LLM_MODEL,
        "system": system or "",
        "prompt": prompt,
        "options": options or config.LLM_OPTIONS,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def _cache_path(key):
    return config.LLM_CACHE_DIR / f"{key}.json"


def is_cached(prompt, system=None, model=None, options=None):
    return _cache_path(cache_key(prompt, system, model, options)).exists()


def generate(prompt, system=None, model=None, options=None, label="llm"):
    """Return the model's reply, from cache if this exact call was made before."""
    model = model or config.LLM_MODEL
    options = options or config.LLM_OPTIONS
    path = _cache_path(cache_key(prompt, system, model, options))
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))["response"]

    import ollama
    t = time.perf_counter()
    reply = ollama.generate(model=model, prompt=prompt, system=system or "", options=options)
    text = reply["response"].strip()
    secs = time.perf_counter() - t
    if config.PRINT_TIMINGS:
        print(f"[timing] {label} ({model}, uncached): {secs:.1f}s")

    # Store the inputs too, so the cache doubles as a log you can inspect.
    config.LLM_CACHE_DIR.mkdir(exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps({"model": model, "system": system, "prompt": prompt, "options": options,
                               "response": text, "seconds": round(secs, 2)}, indent=2), encoding="utf-8")
    os.replace(tmp, path)  # atomic: an interrupted run never leaves a half-written entry
    return text


if __name__ == "__main__":
    t = time.perf_counter()
    print(generate("Reply with exactly one word: ready?", label="smoke test"))
    print(f"first call: {time.perf_counter() - t:.2f}s")
    t = time.perf_counter()
    generate("Reply with exactly one word: ready?")
    print(f"second call (cached): {(time.perf_counter() - t) * 1000:.1f} ms")
