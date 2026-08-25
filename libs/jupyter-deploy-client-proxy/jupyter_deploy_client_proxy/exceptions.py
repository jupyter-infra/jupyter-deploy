"""Exceptions raised by the client proxy."""

from __future__ import annotations


class ProxyError(Exception):
    """Base class for all client-proxy errors."""


class TokenCommandError(ProxyError):
    """The token command failed to run, timed out, exited non-zero, or produced a bad bundle.

    Callers catch this base for "any token-command failure"; the retry loop branches on the
    ``Retryable``/``NotRetryable`` subclasses.
    """


class RetryableTokenCommandError(TokenCommandError):
    """A transient failure (timeout, EX_TEMPFAIL exit, malformed output) — retrying may succeed."""


class NotRetryableTokenCommandError(TokenCommandError):
    """A permanent failure (bad config, missing binary, wrong bundle shape) — retrying will not help."""
