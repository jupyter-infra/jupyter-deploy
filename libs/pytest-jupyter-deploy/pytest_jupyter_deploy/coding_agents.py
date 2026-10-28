"""Prompt the coding agents (Claude Code, Codex) installed on a server, through `jd server exec`.

Both run headless (``claude -p``, ``codex exec``), which skips their first-run dialogs (theme,
trust, onboarding). Callers should assert on a token they ask the model for, never on CLI text,
so that CLI releases cannot break them. ``agent_tui_running`` checks the interactive TUI started
elsewhere (e.g. in a JupyterLab terminal) is still up, again without reading what it renders.

The ``app_*`` helpers probe the credential path the agents depend on in the EC2 templates: a
sidecar publishes short-lived credentials of a Bedrock-only role to a file the jupyter container
reads, and the container itself cannot reach the instance metadata service.
"""

import base64
import contextlib
import json
import shlex
import subprocess
import time
from datetime import datetime
from typing import Any

from pytest_jupyter_deploy.cli import JDCliError
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.files import build_server_exec_cmd

CANARY = "JDPONG"
CANARY_PROMPT = f"Reply with the single word {CANARY} and nothing else."
AGENT_TIMEOUT_S = 300

BEDROCK_SIDECAR_SERVICE = "bedrock-sidecar"
APP_CREDENTIALS_PATH = "/run/bedrock-creds/credentials.json"

# Runs INSIDE the jupyter container (`uv run --with boto3 python -c`, argv: bucket [secret_arn]) and
# resolves credentials through the default chain, so a passing probe proves the jupyter process
# itself holds the Bedrock-only app role -- not the test runner. Region: the container sets
# AWS_REGION, which botocore does not read on its own.
APP_ROLE_PROBE_SCRIPT = """
import json
import os
import sys

import boto3
from botocore.exceptions import ClientError


def denied(call):
    try:
        call()
    except ClientError as e:
        return e.response["Error"]["Code"] in {"AccessDenied", "AccessDeniedException"}
    return False


session = boto3.Session(region_name=os.environ["AWS_REGION"])
bucket = sys.argv[1]
secret_arn = sys.argv[2] if len(sys.argv) > 2 else None
sts = session.client("sts")
bedrock = session.client("bedrock")
s3 = session.client("s3")
secrets = session.client("secretsmanager")
print(json.dumps({
    "arn": sts.get_caller_identity()["Arn"],
    "bedrock_ok": bool(bedrock.list_foundation_models()["modelSummaries"]),
    "s3_denied": denied(lambda: s3.list_objects_v2(Bucket=bucket)),
    "secret_denied": denied(lambda: secrets.get_secret_value(SecretId=secret_arn)) if secret_arn else None,
}))
"""

BEDROCK_PROBE_LOG = "/tmp/bedrock-probe.log"
BEDROCK_PROBE_STOP = "/tmp/bedrock-probe.stop"
# Matches the loop's argv (the log path) but not its own text, so a wrapper shell echoing the
# pattern never counts as the loop.
_BEDROCK_PROBE_PROCESS_PATTERN = "bedrock-probe[.]log"

# Runs INSIDE the jupyter container in the background (argv: log_file stop_file) with one SDK
# session built up front, as a user's long-running kernel would hold it across a credential
# rotation. Appends ``ok <time>`` or ``fail <time> <error>`` every 10 s until the stop file exists.
BEDROCK_PROBE_LOOP_SCRIPT = """
import os
import sys
import time
from datetime import datetime, timezone

import boto3

log_file, stop_file = sys.argv[1], sys.argv[2]
bedrock = boto3.Session(region_name=os.environ["AWS_REGION"]).client("bedrock")
while not os.path.exists(stop_file):
    now = datetime.now(timezone.utc).isoformat()
    try:
        bedrock.list_foundation_models()
        line = f"ok {now}"
    except Exception as e:
        line = f"fail {now} {e}"
    with open(log_file, "a") as f:
        print(line, file=f)
    time.sleep(10)
"""

# Matches the agent's own processes by argv[0] (the codex launcher runs under node, so its
# argv[0] is node and the native binary's is a path), and never pgrep's own pattern argument.
_AGENT_PROCESS_PATTERNS = {"claude": "(^|/)claude( |$)", "codex": "(^|/)codex( |$)"}


def _ask(
    e2e_deployment: EndToEndDeployment, argv: list[str], name: str | None, scope: str | None, timeout_s: int
) -> subprocess.CompletedProcess[str]:
    return e2e_deployment.cli.run_exec_with_retry(
        build_server_exec_cmd([shlex.join(argv)], name=name, scope=scope), timeout_seconds=timeout_s
    )


def ask_claude_code(
    e2e_deployment: EndToEndDeployment,
    prompt: str = CANARY_PROMPT,
    name: str | None = None,
    scope: str | None = None,
    timeout_s: int = AGENT_TIMEOUT_S,
) -> str:
    """Return Claude Code's answer to ``prompt``.

    Raises:
        JDCliError: If Claude Code exits non-zero (e.g. it cannot reach its model).
    """
    return _ask(e2e_deployment, ["claude", "-p", prompt], name, scope, timeout_s).stdout


def ask_codex(
    e2e_deployment: EndToEndDeployment,
    prompt: str = CANARY_PROMPT,
    name: str | None = None,
    scope: str | None = None,
    timeout_s: int = AGENT_TIMEOUT_S,
) -> str:
    """Return Codex's answer to ``prompt``; runs outside a git repository.

    Raises:
        JDCliError: If Codex exits non-zero (e.g. it cannot reach its model).
    """
    return _ask(e2e_deployment, ["codex", "exec", "--skip-git-repo-check", prompt], name, scope, timeout_s).stdout


def agent_tui_running(
    e2e_deployment: EndToEndDeployment, agent: str, name: str | None = None, scope: str | None = None
) -> bool:
    """Return whether a process of ``agent`` ("claude" or "codex") runs on the server.

    Raises:
        JDCliError: If the check itself fails (e.g. the image lacks pgrep), rather than
            reporting the agent as stopped.
    """
    cmd = build_server_exec_cmd([shlex.join(["pgrep", "-f", _AGENT_PROCESS_PATTERNS[agent]])], name=name, scope=scope)
    try:
        e2e_deployment.cli.run_exec_with_retry(cmd)
    except JDCliError as e:
        # pgrep exits 1 when nothing matches.
        if isinstance(e.__cause__, subprocess.CalledProcessError) and e.__cause__.returncode == 1:
            return False
        raise
    return True


def stop_agent_tui(
    e2e_deployment: EndToEndDeployment, agent: str, name: str | None = None, scope: str | None = None
) -> None:
    """Kill every process of ``agent`` on the server; a no-op when none runs."""
    cmd = build_server_exec_cmd([shlex.join(["pkill", "-f", _AGENT_PROCESS_PATTERNS[agent]])], name=name, scope=scope)
    with contextlib.suppress(JDCliError):
        e2e_deployment.cli.run_exec_with_retry(cmd)


def _exec_stdout(e2e_deployment: EndToEndDeployment, argv: list[str], timeout_s: int | None = None) -> str:
    # rich wraps `jd server exec` output at 80 columns when stdout is not a terminal; a wrapped
    # session token is not JSON any more.
    return e2e_deployment.cli.run_command(
        build_server_exec_cmd([shlex.join(argv)]), timeout_seconds=timeout_s, env={"COLUMNS": "8192"}
    ).stdout


def exec_stdout_value(stdout: str) -> str:
    """Return the one value a `jd server exec` printed, skipping the rich rules around it."""
    for line in stdout.splitlines():
        if line.strip() and not line.startswith("─"):
            return line.strip()
    raise AssertionError(f"No value in server exec output:\n{stdout}")


def _json_line(stdout: str) -> dict[str, Any]:
    for line in stdout.splitlines():
        if line.startswith("{"):
            parsed = json.loads(line)
            assert isinstance(parsed, dict), f"Expected a JSON object, got {parsed!r}"
            return parsed
    raise AssertionError(f"No JSON object line in server exec output:\n{stdout}")


def read_app_credentials(e2e_deployment: EndToEndDeployment) -> dict[str, Any]:
    """Return the credentials file the sidecar publishes, as the jupyter container sees it."""
    return _json_line(_exec_stdout(e2e_deployment, ["cat", APP_CREDENTIALS_PATH]))


def credentials_expiration(credentials: dict[str, Any]) -> datetime:
    """Parse the ``Expiration`` of a credentials file (ISO-8601 with an offset, ``+00:00`` as the AWS CLI writes it)."""
    return datetime.fromisoformat(credentials["Expiration"])


def wait_for_rotated_app_credentials(
    e2e_deployment: EndToEndDeployment, previous_access_key_id: str, timeout_s: int = 120, interval_s: int = 5
) -> dict[str, Any]:
    """Return the credentials once their ``AccessKeyId`` differs from ``previous_access_key_id``.

    Raises:
        AssertionError: If the sidecar has not published a new key within ``timeout_s``.
    """
    deadline = time.monotonic() + timeout_s
    while True:
        credentials = read_app_credentials(e2e_deployment)
        if credentials["AccessKeyId"] != previous_access_key_id:
            return credentials
        if time.monotonic() >= deadline:
            raise AssertionError(f"AccessKeyId {previous_access_key_id} still published after {timeout_s}s")
        time.sleep(interval_s)


def imds_reachable(e2e_deployment: EndToEndDeployment) -> bool:
    """Return whether the jupyter container can get an IMDSv2 token; the templates must say no."""
    argv = [
        "curl",
        "-sS",
        "-m",
        "3",
        "-X",
        "PUT",
        "http://169.254.169.254/latest/api/token",
        "-H",
        "X-aws-ec2-metadata-token-ttl-seconds: 60",
    ]
    try:
        e2e_deployment.cli.run_command(build_server_exec_cmd([shlex.join(argv)]))
    except JDCliError as e:
        # Only curl's own "could not connect" exits mean unreachable (28 timeout, 7 refused); a
        # missing curl or a dead host must not pass as "blocked".
        if isinstance(e.__cause__, subprocess.CalledProcessError) and e.__cause__.returncode in (7, 28):
            return False
        raise
    return True


def app_role_access(e2e_deployment: EndToEndDeployment, bucket: str, secret_arn: str | None = None) -> dict[str, Any]:
    """Run ``APP_ROLE_PROBE_SCRIPT`` in the jupyter container and return its JSON report.

    ``bucket`` is a bucket of the deployment the app role must NOT read; ``secret_arn`` likewise
    (``secret_denied`` is None when no secret is given).
    """
    # base64 keeps the multi-line script a single shell word through SSM and `docker exec`.
    encoded = base64.b64encode(APP_ROLE_PROBE_SCRIPT.encode()).decode()
    argv = ["uv", "run", "--with", "boto3", "python", "-c", f"import base64; exec(base64.b64decode('{encoded}'))"]
    argv.append(bucket)
    if secret_arn is not None:
        argv.append(secret_arn)
    return _json_line(_exec_stdout(e2e_deployment, argv, timeout_s=AGENT_TIMEOUT_S))


def ask_agent_expecting_failure(e2e_deployment: EndToEndDeployment, argv: list[str]) -> str:
    """Run an agent command that must fail (e.g. Bedrock disabled) and return its flattened output.

    Raises:
        AssertionError: If the agent succeeds.
    """
    return e2e_deployment.cli.run_command_expecting_failure(
        build_server_exec_cmd([shlex.join(argv)]), timeout_seconds=AGENT_TIMEOUT_S
    )


def restart_service(e2e_deployment: EndToEndDeployment, name: str) -> None:
    e2e_deployment.cli.run_command(["jupyter-deploy", "server", "restart", "--service", name])


def _probe_lines(e2e_deployment: EndToEndDeployment) -> list[str]:
    try:
        stdout = _exec_stdout(e2e_deployment, ["cat", BEDROCK_PROBE_LOG])
    except JDCliError:
        return []  # not written yet
    return [line for line in stdout.splitlines() if line.startswith(("ok ", "fail "))]


def _probe_loop_running(e2e_deployment: EndToEndDeployment) -> bool:
    try:
        e2e_deployment.cli.run_command(
            build_server_exec_cmd([shlex.join(["pgrep", "-f", _BEDROCK_PROBE_PROCESS_PATTERN])])
        )
    except JDCliError as e:
        if isinstance(e.__cause__, subprocess.CalledProcessError) and e.__cause__.returncode == 1:
            return False
        raise
    return True


def start_bedrock_probe_loop(e2e_deployment: EndToEndDeployment, timeout_s: int = 120) -> None:
    """Start ``BEDROCK_PROBE_LOOP_SCRIPT`` detached in the jupyter container; return once it logged its first probe.

    Raises:
        AssertionError: If nothing is logged within ``timeout_s`` (``uv run --with boto3`` can take a
            minute on a cold cache, hence the generous default).
    """
    encoded = base64.b64encode(BEDROCK_PROBE_LOOP_SCRIPT.encode()).decode()
    script = (
        f"rm -f {BEDROCK_PROBE_LOG} {BEDROCK_PROBE_STOP}; "
        f"nohup uv run --with boto3 python -c \"import base64; exec(base64.b64decode('{encoded}'))\" "
        f"{BEDROCK_PROBE_LOG} {BEDROCK_PROBE_STOP} </dev/null >/dev/null 2>&1 &"
    )
    e2e_deployment.cli.run_command(build_server_exec_cmd([shlex.join(["sh", "-c", script])]))
    deadline = time.monotonic() + timeout_s
    while not _probe_lines(e2e_deployment):
        if time.monotonic() >= deadline:
            raise AssertionError(f"bedrock probe loop logged nothing within {timeout_s}s")
        time.sleep(5)


def stop_bedrock_probe_loop(e2e_deployment: EndToEndDeployment, timeout_s: int = 20) -> list[str]:
    """Stop the probe loop and return its log lines (``ok <time>`` / ``fail <time> <error>``).

    Raises:
        AssertionError: If the loop is still running after ``timeout_s``.
    """
    _exec_stdout(e2e_deployment, ["touch", BEDROCK_PROBE_STOP])
    deadline = time.monotonic() + timeout_s
    while _probe_loop_running(e2e_deployment):
        if time.monotonic() >= deadline:
            raise AssertionError(f"bedrock probe loop still running {timeout_s}s after {BEDROCK_PROBE_STOP}")
        time.sleep(2)
    return _probe_lines(e2e_deployment)
