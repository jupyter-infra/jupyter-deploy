"""Print the best model Codex's own catalog offers for an inference profile prefix.

Usage: codex debug models | python3 pick-codex-model.py <prefix> <patterns>
<patterns> is a comma-separated list of IAM wildcards on the unprefixed model ID
(bedrock_model_patterns); only models they allow are considered. Ranks by the
catalog's priority, lowest first; entries without one rank last, in catalog order.
Prints nothing when no model qualifies.
"""

import fnmatch
import json
import math
import sys

prefix = f"{sys.argv[1]}."
patterns = [p for p in sys.argv[2].split(",") if p]
models = json.load(sys.stdin)["models"]
allowed = [
    m
    for m in models
    if m["slug"].startswith(prefix) and any(fnmatch.fnmatchcase(m["slug"][len(prefix) :], p) for p in patterns)
]
ranked = sorted(allowed, key=lambda m: m["priority"] if isinstance(m.get("priority"), (int, float)) else math.inf)
if ranked:
    print(ranked[0]["slug"])
