"""Pin Codex's model in its system config to the best one this Codex release offers on Bedrock.

Usage: python3 pick-codex-model.py <prefix> <patterns> <config_path>
<prefix> is the inference profile prefix (us, global, eu, ...); <patterns> a comma-separated list
of IAM wildcards on the unprefixed model ID (bedrock_model_patterns). Replaces @CODEX_MODEL@ in
<config_path> with the allowed slug `codex debug models` ranks best (lowest priority; entries
without one last, in catalog order). Where Codex has nothing to use, an `unset: <reason>`
placeholder makes its error name the fix: without a model line it would fall back to a built-in
default that IAM denies. Exits 1, failing the image build, when a usable prefix and allowed
patterns match no catalog entry. The codex binary comes from $CODEX_BIN (default: codex).
"""

import fnmatch
import json
import math
import os
import subprocess
import sys
from pathlib import Path

prefix, patterns_arg, config_path = sys.argv[1:4]
patterns = [p for p in patterns_arg.split(",") if p]


def pick() -> str:
    if not patterns:
        return "unset: bedrock_enabled is false or no openai model allowed by bedrock_model_patterns"
    if prefix not in ("us", "global"):
        return f"unset: no {prefix or 'geographic'} OpenAI inference profiles, set bedrock_inference_scope to global"
    catalog = subprocess.run(
        [os.environ.get("CODEX_BIN", "codex"), "debug", "models"], capture_output=True, text=True, check=True
    )
    dotted = f"{prefix}."
    allowed = [
        m
        for m in json.loads(catalog.stdout)["models"]
        if m["slug"].startswith(dotted) and any(fnmatch.fnmatchcase(m["slug"][len(dotted) :], p) for p in patterns)
    ]
    ranked = sorted(allowed, key=lambda m: m["priority"] if isinstance(m.get("priority"), (int, float)) else math.inf)
    if not ranked:
        sys.exit(f"codex debug models lists no {prefix}. model allowed by {patterns_arg}")
    return str(ranked[0]["slug"])


config = Path(config_path)
config.write_text(config.read_text().replace("@CODEX_MODEL@", pick()))
