import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from jupyter_deploy_client_proxy.constants import RETRYABLE_EXIT_CODE
from jupyter_deploy_client_proxy.credentials.credential import (
    _get_backoff_delay_seconds,
    fetch_bundle,
    fetch_bundle_with_retries,
)
from jupyter_deploy_client_proxy.exceptions import (
    NotRetryableTokenCommandError,
    RetryableTokenCommandError,
    TokenCommandError,
)
from jupyter_deploy_client_proxy.logger.factory import create_logger

BUNDLE = {
    "host": "10.0.0.1",
    "port": 443,
    "ca_cert": "",
    "headers": {"Authorization": "Bearer x"},
    "expires_at": "2026-06-10T18:01:00Z",
}


def _emit_argv(payload: str) -> list[str]:
    """An argv that prints ``payload`` verbatim on stdout, portably."""
    return [sys.executable, "-c", f"import sys; sys.stdout.write({payload!r})"]


def _exit_argv(code: int) -> list[str]:
    """An argv that exits with ``code`` (writing 'boom' to stderr)."""
    return [sys.executable, "-c", f"import sys; sys.stderr.write('boom'); sys.exit({code})"]


def _counting_argv(dir_path: str, exit_code: int) -> list[str]:
    """An argv that records each invocation in a counter file, then exits with ``exit_code``."""
    counter = os.path.join(dir_path, "count")
    script = os.path.join(dir_path, "counter.py")
    src = (
        "import os, sys\n"
        f"c = {counter!r}\n"
        "n = int(open(c).read()) if os.path.exists(c) else 0\n"
        "open(c, 'w').write(str(n + 1))\n"
        f"sys.exit({exit_code})\n"
    )
    with open(script, "w") as f:
        f.write(src)
    return [sys.executable, script]


def _fail_then_succeed_argv(dir_path: str, fail_times: int, payload: str) -> list[str]:
    """An argv that exits with a retryable code its first ``fail_times`` calls, then prints ``payload``."""
    counter = os.path.join(dir_path, "count")
    script = os.path.join(dir_path, "flaky.py")
    src = (
        "import os, sys\n"
        f"c = {counter!r}\n"
        "n = int(open(c).read()) if os.path.exists(c) else 0\n"
        "open(c, 'w').write(str(n + 1))\n"
        f"if n < {fail_times}:\n"
        f"    sys.stderr.write('transient'); sys.exit({RETRYABLE_EXIT_CODE})\n"
        f"sys.stdout.write({payload!r})\n"
    )
    with open(script, "w") as f:
        f.write(src)
    return [sys.executable, script]


def _count(dir_path: str) -> int:
    return int(Path(dir_path, "count").read_text())


class _LoggerTestCase(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = self._tmp.name
        self.logger = create_logger("DEBUG", Path(self.tmp) / "logs")

    async def asyncTearDown(self) -> None:
        await self.logger.close()

    async def log_text(self) -> str:
        await self.logger.flush()  # drain fire-and-forget writes before reading
        logs = sorted((Path(self.tmp) / "logs").glob("[0-9][0-9][0-9][0-9].log"))
        return "".join(p.read_text() for p in logs)


class TestFetchBundle(_LoggerTestCase):
    async def test_parses_command_stdout(self) -> None:
        bundle = await fetch_bundle(_emit_argv(json.dumps(BUNDLE)), self.logger)
        self.assertEqual(bundle.host, "10.0.0.1")
        self.assertEqual(bundle.headers["Authorization"], "Bearer x")

    async def test_success_logs_timing_at_debug(self) -> None:
        await fetch_bundle(_emit_argv(json.dumps(BUNDLE)), self.logger)
        self.assertIn("produced a valid bundle in", await self.log_text())

    async def test_empty_argv_is_not_retryable(self) -> None:
        with self.assertRaises(NotRetryableTokenCommandError):
            await fetch_bundle([], self.logger)

    async def test_missing_binary_is_not_retryable(self) -> None:
        with self.assertRaises(NotRetryableTokenCommandError):
            await fetch_bundle(["this-binary-does-not-exist-xyz"], self.logger)

    async def test_tempfail_exit_is_retryable_and_warns(self) -> None:
        with self.assertRaises(RetryableTokenCommandError):
            await fetch_bundle(_exit_argv(RETRYABLE_EXIT_CODE), self.logger)
        self.assertIn("WARNING", await self.log_text())

    async def test_other_nonzero_exit_is_not_retryable_and_errors(self) -> None:
        with self.assertRaises(NotRetryableTokenCommandError) as ctx:
            await fetch_bundle(_exit_argv(3), self.logger)
        self.assertIn("boom", str(ctx.exception))
        self.assertIn("ERROR", await self.log_text())

    async def test_timeout_is_retryable(self) -> None:
        argv = [sys.executable, "-c", "import time; time.sleep(5)"]
        with self.assertRaises(RetryableTokenCommandError):
            await fetch_bundle(argv, self.logger, timeout=0.2)

    async def test_invalid_json_is_retryable(self) -> None:
        with self.assertRaises(RetryableTokenCommandError):
            await fetch_bundle(_emit_argv("not json"), self.logger)

    async def test_schema_invalid_is_not_retryable(self) -> None:
        payload = json.dumps({k: v for k, v in BUNDLE.items() if k != "host"})
        with self.assertRaises(NotRetryableTokenCommandError):
            await fetch_bundle(_emit_argv(payload), self.logger)


class TestGetBackoffDelaySeconds(unittest.TestCase):
    def test_exponential_growth(self) -> None:
        self.assertEqual(_get_backoff_delay_seconds(0, base=0.5), 0.5)
        self.assertEqual(_get_backoff_delay_seconds(1, base=0.5), 1.0)
        self.assertEqual(_get_backoff_delay_seconds(2, base=0.5), 2.0)

    def test_capped(self) -> None:
        self.assertEqual(_get_backoff_delay_seconds(20, base=0.5, cap=30.0), 30.0)

    def test_negative_attempt_raises(self) -> None:
        with self.assertRaises(ValueError):
            _get_backoff_delay_seconds(-1)


class TestFetchBundleWithRetries(_LoggerTestCase):
    async def test_returns_on_first_success(self) -> None:
        bundle = await fetch_bundle_with_retries(_emit_argv(json.dumps(BUNDLE)), self.logger, base_delay_seconds=0.001)
        self.assertEqual(bundle.host, "10.0.0.1")

    async def test_retries_retryable_until_success(self) -> None:
        argv = _fail_then_succeed_argv(self.tmp, fail_times=2, payload=json.dumps(BUNDLE))
        bundle = await fetch_bundle_with_retries(argv, self.logger, base_delay_seconds=0.0, max_attempts=3)
        self.assertEqual(bundle.host, "10.0.0.1")

    async def test_does_not_retry_nonretryable(self) -> None:
        argv = _counting_argv(self.tmp, exit_code=1)  # non-retryable
        with self.assertRaises(NotRetryableTokenCommandError):
            await fetch_bundle_with_retries(argv, self.logger, base_delay_seconds=0.0, max_attempts=5)
        self.assertEqual(_count(self.tmp), 1)  # tried once despite max_attempts=5

    async def test_exhausts_retryable_then_errors(self) -> None:
        argv = _counting_argv(self.tmp, exit_code=RETRYABLE_EXIT_CODE)
        with self.assertRaises(RetryableTokenCommandError):
            await fetch_bundle_with_retries(argv, self.logger, base_delay_seconds=0.0, max_attempts=3)
        self.assertEqual(_count(self.tmp), 3)  # exhausted all attempts
        self.assertIn("ERROR", await self.log_text())

    async def test_base_class_catches_either(self) -> None:
        with self.assertRaises(TokenCommandError):
            await fetch_bundle_with_retries(_exit_argv(1), self.logger)
