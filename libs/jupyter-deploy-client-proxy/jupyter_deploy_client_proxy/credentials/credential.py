"""The exec-credential loop: run the token command and parse the bundle.

This is the boundary that keeps the proxy cloud-blind — it runs an opaque command
and parses JSON, knowing nothing about STS, AWS, or any provider.
"""

from __future__ import annotations

import asyncio
import json
import time

from pydantic import ValidationError

from jupyter_deploy_client_proxy.constants import (
    DEFAULT_BASE_DELAY_SECONDS,
    DEFAULT_MAX_DELAY_SECONDS,
    DEFAULT_TOKEN_COMMAND_TIMEOUT_SECONDS,
    RETRYABLE_EXIT_CODE,
)
from jupyter_deploy_client_proxy.credentials.bundle import ConnectBundle
from jupyter_deploy_client_proxy.exceptions import NotRetryableTokenCommandError, RetryableTokenCommandError
from jupyter_deploy_client_proxy.logger.proxy_logger import ProxyLogger


def _get_backoff_delay_seconds(
    attempt: int, base: float = DEFAULT_BASE_DELAY_SECONDS, cap: float = DEFAULT_MAX_DELAY_SECONDS
) -> float:
    """Exponential backoff for retry ``attempt`` (0-indexed), capped at ``cap``."""
    if attempt < 0:
        raise ValueError("attempt must be >= 0")
    return min(cap, base * float(2**attempt))


async def fetch_bundle(
    argv: list[str],
    logger: ProxyLogger,
    timeout: float = DEFAULT_TOKEN_COMMAND_TIMEOUT_SECONDS,
) -> ConnectBundle:
    """Run the token command once and parse its stdout into a ConnectBundle.

    Args:
        argv: the already-split command (e.g. ``["jd", "proxy", "connect-info"]``).
        logger: aiologger logger; debug-logs the invocation + timing, warns on failure.
        timeout: seconds to wait before killing the command.

    Raises:
        RetryableTokenCommandError: on a transient failure (timeout, EX_TEMPFAIL, malformed output).
        NotRetryableTokenCommandError: on a permanent failure (bad config, missing binary, wrong shape).
    """
    if not argv:
        raise NotRetryableTokenCommandError("token command is empty")

    started = time.monotonic()
    try:
        logger.debug(f"running token command: {argv}")

        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
        except (OSError, ValueError) as e:
            # Cannot start (e.g. binary missing) — retrying won't help.
            raise NotRetryableTokenCommandError(f"failed to start token command {argv!r}: {e}") from e

        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout)
        except TimeoutError as e:
            proc.kill()
            await proc.wait()
            raise RetryableTokenCommandError(f"token command {argv!r} timed out after {timeout}s") from e

        if proc.returncode != 0:
            detail = stderr.decode(errors="replace").strip()
            # The command signals transience via EX_TEMPFAIL; any other non-zero is permanent.
            msg = f"token command {argv!r} exited {proc.returncode}: {detail}"
            if proc.returncode == RETRYABLE_EXIT_CODE:
                raise RetryableTokenCommandError(msg)
            raise NotRetryableTokenCommandError(msg)

        try:
            data = json.loads(stdout.decode(errors="replace"))
        except json.JSONDecodeError as e:
            # Malformed/partial output could be transient.
            raise RetryableTokenCommandError(f"token command did not emit valid JSON: {e}") from e
        try:
            bundle = ConnectBundle.model_validate(data)
        except ValidationError as e:
            # Wrong shape is deterministic — retrying yields the same bad bundle.
            raise NotRetryableTokenCommandError(f"token command emitted an invalid bundle: {e}") from e
    except RetryableTokenCommandError as e:
        logger.warning(f"token command failed (retryable): {e}")
        raise
    except NotRetryableTokenCommandError as e:
        logger.error(f"token command failed (not retryable): {e}")
        raise

    logger.debug(f"token command produced a valid bundle in {time.monotonic() - started:.3f}s")
    return bundle


async def fetch_bundle_with_retries(
    argv: list[str],
    logger: ProxyLogger,
    timeout: float = DEFAULT_TOKEN_COMMAND_TIMEOUT_SECONDS,
    base_delay_seconds: float = DEFAULT_BASE_DELAY_SECONDS,
    max_delay_seconds: float = DEFAULT_MAX_DELAY_SECONDS,
    max_attempts: int = 1,
) -> ConnectBundle:
    """Fetch a bundle, retrying with exponential backoff on token-command/parse failures.

    Only retryable failures are retried, up to ``max_attempts`` (default 1 = no retry).
    Non-retryable failures raise immediately (already logged at error by ``fetch_bundle``);
    exhausting the retryable attempts logs at error and re-raises.
    """
    attempt = 0
    while True:
        try:
            return await fetch_bundle(argv, logger, timeout=timeout)
        except NotRetryableTokenCommandError:
            raise  # permanent; fetch_bundle already logged it at error
        except RetryableTokenCommandError as e:
            attempt += 1
            if attempt >= max_attempts:
                logger.error(f"token command failed after {attempt} retryable attempt(s): {e}")
                raise
            delay = _get_backoff_delay_seconds(attempt - 1, base=base_delay_seconds, cap=max_delay_seconds)
            logger.info(f"retrying token command in {delay:.0f}s (attempt {attempt + 1}/{max_attempts})")
            await asyncio.sleep(delay)
