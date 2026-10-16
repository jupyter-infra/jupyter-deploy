"""E2E tests for the auth boundary — direct requests to the instance, no allowlist mutation.

This template's security model has no analogue in the base template. There is no OAuth, no public
URL, and no network fence: the security group opens ``:443`` to the world on purpose. The boundary
is (a) TLS pinned to a self-signed cert whose PEM is published to SSM, and (b) a Traefik ForwardAuth
sidecar that replays a presigned ``sts:GetCallerIdentity`` token and authorizes the ARN STS returns
against this deployment's IAM allowlists.

**Scope: this file only ever sends requests.** It never runs `jd users` / `jd teams`, so it needs no
allowlist snapshot, cannot lock the caller out, and is fast — nearly every case is rejected before
the sidecar makes any outbound call. The allowlist itself is exercised in ``test_teams.py`` (the
positive and negative paths for a role caller, which is what CI runs as) and ``test_users.py``.

The sidecar's contract is a status code, so these tests *are* the client: a stdlib HTTPS connection
trusting exactly the pinned PEM (``local_proxy.requests.pinned_request``). Driving them through the
real proxy would add a part that can mask the very status code under assertion.

Omitted: covered by the base template suite (`test_users.py`, `test_org_and_teams.py`)
  The GitHub-identity allowlist semantics (org membership, team membership, "cannot remove the last
  user while no org is allowlisted"). None of it applies: authorization here is by IAM role/user
  name within one AWS account, with no org/team concept and no such interlock.

Not testable here, and deliberately skipped:
  - **Cross-account** (an identically named role in another account, which ``allows()`` rejects on
    the ``accountID`` check) — needs a second AWS account.
  - **Non-role/non-user principals** (root, federated-user, service principal -> ``kind == ""`` ->
    403) — cannot be produced from the CI identity.
  - **503 on STS unavailability** — would require faulting STS.

  All three are pure ``config.allows`` / error-mapping logic with no I/O, so they belong in Go unit
  tests next to the sidecar. There is no `go test` target in this repo yet (see the note in
  ``template/services/auth-sidecar/main_test.go``), so they are currently uncovered — stated here
  rather than left implied.

Deliberately elsewhere:
  - ``test_cert_pin_stable_across_host_restart`` lives in ``test_host.py``, which owns the suite's
    single EC2 stop/start cycle.

How the tokens here are crafted
-------------------------------
A token is ``k8s-aws-v1.`` + base64url of a presigned ``sts:GetCallerIdentity`` URL. Its SigV4
query string — ``X-Amz-Date``, ``X-Amz-Expires``, ``X-Amz-Credential``, ``X-Amz-SignedHeaders`` —
is **covered by** ``X-Amz-Signature``, and the ``x-k8s-aws-id`` binding header is signed too. Two
consequences shape every test in this file:

* **Only the expiry is choosable.** ``mint_token(expires_in_seconds=N)`` sets ``X-Amz-Expires``
  at signing time. ``X-Amz-Date`` has no such knob — it is whatever the signer stamps as "now" —
  so the only honest way to age a token is to wait.
* **``retarget_token`` rewrites fields but never re-signs.** That is fine for every 401 case,
  because ``verify()`` runs its structural checks (host pin, action, expiry bounds, date bounds)
  BEFORE it contacts STS, so a broken signature is irrelevant to the assertion and costs no
  outbound call. It is useless for a 200: that needs STS to validate the signature, so the token
  must be genuinely signed and genuinely old — see
  ``test_token_within_clock_skew_allowance_is_accepted``, the one test here that sleeps.

The same asymmetry is why none of this is an attacker's tool. Re-dating or extending a *captured*
token invalidates the signature, so STS rejects the replay; the crafted cases below only ever
demonstrate the sidecar's own offline checks. The threat the expiry cap addresses is not forgery
but a legitimate client minting an over-long bearer credential — see
``test_token_with_unbounded_expiry_is_rejected_401``.
"""

import ssl
import time

import pytest
from pytest_jupyter_deploy.auth_sidecars.aws_auth_sidecar import (
    BINDING_HEADER,
    MAX_TOKEN_EXPIRY_SECONDS,
    TOKEN_PREFIX,
    auth_headers,
    mint_token,
    retarget_token,
)
from pytest_jupyter_deploy.local_proxy.jupyterlab import AUTH_PROBE_PATH
from pytest_jupyter_deploy.local_proxy.requests import (
    cert_fingerprint,
    pinned_request,
    served_cert_pem,
    system_trust_request,
    unverified_request,
)

pytestmark = pytest.mark.proxy

# The sidecar's own X-Amz-Date format and skew allowance (main.go). Duplicated so a test cannot
# silently follow a change to the value it is asserting.
_AMZ_DATE_FORMAT = "%Y%m%dT%H%M%SZ"
_SIDECAR_CLOCK_SKEW_SECONDS = 60


def _probe(bundle: dict, headers: dict[str, str] | None) -> tuple[int, str]:
    """Issue one pinned request to the deployment with exactly ``headers``."""
    return pinned_request(bundle["host"], bundle["port"], bundle["ca_cert"], path=AUTH_PROBE_PATH, headers=headers)


def _backdate(token: str, seconds_ago: int) -> str:
    """Return ``token`` with its ``X-Amz-Date`` rewritten to ``seconds_ago`` in the past.

    Invalidates the signature (the date is signed), so this is only usable where the expected
    answer is 401 — the sidecar's date check runs before STS is ever contacted. Negative
    ``seconds_ago`` dates the token into the future.
    """
    signed_at = time.strftime(_AMZ_DATE_FORMAT, time.gmtime(time.time() - seconds_ago))
    return retarget_token(token, query={"X-Amz-Date": signed_at})


# --------------------------------------------------------------------------- offline rejections
# `verify()` runs every structural check before it contacts STS, so these need no valid
# credentials, make no outbound call, and cannot flake on STS.


def test_missing_authorization_is_rejected_401(connect_bundle: dict) -> None:
    """No ``Authorization`` header at all -> 401 (no token to check, no STS call)."""
    status, _ = _probe(connect_bundle, headers={BINDING_HEADER: connect_bundle["headers"][BINDING_HEADER]})
    assert status == 401, f"Expected 401 with no Authorization header, got {status}"


def test_wrong_binding_id_is_rejected_401(connect_bundle: dict) -> None:
    """A binding header that is not this deployment's id -> 401, by local compare.

    The cross-deployment replay defense. Worth stating precisely: ``verify()`` compares the header
    to ``DEPLOYMENT_ID`` as its FIRST check, before any STS call — so the defense holds even for a
    token STS would happily have accepted, and costs nothing to enforce.
    """
    headers = dict(connect_bundle["headers"])
    headers[BINDING_HEADER] = "not-this-deployment"

    status, _ = _probe(connect_bundle, headers=headers)
    assert status == 401, f"Expected 401 for a mismatched binding id, got {status}"


@pytest.mark.parametrize(
    ("token", "reason"),
    [
        ("not-a-token-at-all", "missing the k8s-aws-v1. prefix"),
        (f"{TOKEN_PREFIX}!!!not-base64url!!!", "not valid base64url"),
        (f"{TOKEN_PREFIX}", "empty token body"),
    ],
)
def test_malformed_token_is_rejected_401(connect_bundle: dict, token: str, reason: str) -> None:
    """A token that is not a well-formed presigned URL -> 401."""
    headers = auth_headers(token, connect_bundle["headers"][BINDING_HEADER])

    status, _ = _probe(connect_bundle, headers=headers)
    assert status == 401, f"Expected 401 for a token {reason}, got {status}"


def test_token_pointing_off_sts_is_rejected_401(connect_bundle: dict, deployment_id: str, aws_region: str) -> None:
    """A token whose embedded URL targets a non-STS host -> 401, with no outbound call made.

    The SSRF belt. The token IS a URL the sidecar fetches, so without the host pin an attacker
    could aim the sidecar at any host — internal services, link-local metadata — and use it as a
    confused deputy. ``verify()`` compares the decoded host to the pinned STS endpoint and replays
    only ever to that endpoint, so this is rejected before any socket is opened.
    """
    off_sts = retarget_token(mint_token(deployment_id, aws_region), host="evil.example.com")

    status, _ = _probe(connect_bundle, headers=auth_headers(off_sts, deployment_id))
    assert status == 401, f"Expected 401 for a token pointing off the pinned STS host, got {status}"


def test_token_with_wrong_action_is_rejected_401(connect_bundle: dict, deployment_id: str, aws_region: str) -> None:
    """A presigned URL for an action other than GetCallerIdentity -> 401.

    The sidecar's contract is "prove who you are", not "act on the caller's behalf". Accepting an
    arbitrary presigned action would turn it into a general-purpose STS relay.
    """
    wrong_action = retarget_token(mint_token(deployment_id, aws_region), query={"Action": "AssumeRole"})

    status, _ = _probe(connect_bundle, headers=auth_headers(wrong_action, deployment_id))
    assert status == 401, f"Expected 401 for Action=AssumeRole, got {status}"


@pytest.mark.parametrize("expires", ["0", "-1", str(MAX_TOKEN_EXPIRY_SECONDS + 1), "86400", ""])
def test_token_with_unbounded_expiry_is_rejected_401(
    connect_bundle: dict, deployment_id: str, aws_region: str, expires: str
) -> None:
    """``X-Amz-Expires`` outside ``0 < n <= 900`` -> 401.

    The unbounded-expiry footgun: a presigned GetCallerIdentity URL is a bearer credential for as
    long as it is honoured, so a client that minted a 12-hour token would hand out a 12-hour key to
    the app. The sidecar refuses one regardless of what the client chose.
    """
    unbounded = retarget_token(mint_token(deployment_id, aws_region), query={"X-Amz-Expires": expires})

    status, _ = _probe(connect_bundle, headers=auth_headers(unbounded, deployment_id))
    assert status == 401, f"Expected 401 for X-Amz-Expires={expires!r}, got {status}"


def test_token_past_its_signed_lifetime_is_rejected_401(
    connect_bundle: dict, deployment_id: str, aws_region: str
) -> None:
    """A token whose ``X-Amz-Date + X-Amz-Expires`` has elapsed -> 401.

    **The sidecar is the only thing enforcing this.** Measured against live STS: a presigned
    GetCallerIdentity URL declaring ``X-Amz-Expires=1`` still authenticates a minute later — STS
    honours only its own SigV4 window (~15 min of skew on ``X-Amz-Date``), not the lifetime the
    client asked for. Since the token is a bearer credential, without a local check anyone who
    captured one would get that whole window regardless of the 60s the proxy minted it for.

    Backdating ``X-Amz-Date`` rather than sleeping keeps this deterministic and instant: both
    fields are inside the signature, so a real attacker cannot re-date a captured token — but the
    sidecar rejects this offline, before the signature is ever checked.
    """
    stale = _backdate(mint_token(deployment_id, aws_region, expires_in_seconds=60), seconds_ago=1800)

    status, _ = _probe(connect_bundle, headers=auth_headers(stale, deployment_id))
    assert status == 401, f"Expected 401 for a token past its signed lifetime, got {status}"


def test_token_signed_in_the_future_is_rejected_401(connect_bundle: dict, deployment_id: str, aws_region: str) -> None:
    """A token signed far in the future -> 401 — the other half of the lifetime window.

    Without an upper bound on skew, a token dated hours ahead would stay valid for hours: the
    "expired" check alone can be defeated by moving the date forward, not back.
    """
    future = _backdate(mint_token(deployment_id, aws_region), seconds_ago=-3600)

    status, _ = _probe(connect_bundle, headers=auth_headers(future, deployment_id))
    assert status == 401, f"Expected 401 for a token signed in the future, got {status}"


def test_token_within_clock_skew_allowance_is_accepted(
    connect_bundle: dict, deployment_id: str, aws_region: str
) -> None:
    """A token just past its declared expiry but inside the skew allowance still works.

    The deliberate slack in the check above: the signer is the user's laptop, whose clock this host
    does not control. Without it, a laptop a few seconds ahead would see every request rejected —
    the tightening must not become a new failure mode for legitimate callers.

    This one has to **sleep** rather than re-date the token, unlike every rejection test above.
    Rewriting ``X-Amz-Date`` invalidates the signature, which is fine when the expected answer is
    401 (the sidecar rejects offline, before the signature matters) but makes a 200 impossible. So
    the token is genuinely signed and genuinely old.

    It also depends on STS still accepting a replay past the declared expiry — the same measured
    behavior that motivates the sidecar's local check. If AWS ever starts honouring
    ``X-Amz-Expires``, this flips to 401; that would mean the sidecar's check had become redundant,
    which is worth learning from a failure here rather than assuming either way.
    """
    # The expiry is set at mint time (it is a signed field with a knob); the signing DATE has no
    # knob at all, so age can only be produced by waiting. A third of the allowance keeps this
    # clear of the boundary — the claim is "inside the window", not "exactly on it".
    token_lifetime = 5
    age = token_lifetime + _SIDECAR_CLOCK_SKEW_SECONDS // 3
    token = mint_token(deployment_id, aws_region, expires_in_seconds=token_lifetime)
    time.sleep(age)

    status, _ = _probe(connect_bundle, headers=auth_headers(token, deployment_id))
    assert status == 200, (
        f"Expected 200 for a validly-signed token {age}s old with a {token_lifetime}s declared "
        f"expiry (inside the {_SIDECAR_CLOCK_SKEW_SECONDS}s skew allowance), got {status}"
    )


# --------------------------------------------------------------------------- the STS round-trip


def test_token_sts_refuses_is_401_not_403(connect_bundle: dict, deployment_id: str, aws_region: str) -> None:
    """A token STS refuses -> 401 (authentication), never 403 (authorization).

    The one negative that exercises the **STS round-trip itself** and the sidecar's mapping of its
    answer; everything above is rejected before any outbound call, so without this the
    ``replayToSTS`` error path would be untested against the real service.

    The distinction is operational, not pedantic, but NOT because the proxy acts on it — the proxy is
    deliberately status-agnostic (it forwards ``upstream.status`` verbatim and refreshes credentials
    on a timer, never on a 401). It matters because the status is the only thing that tells a caller
    *which* of two unrelated fixes they need: 401 means "your credential was not accepted" (re-mint —
    the token expired, the binding is wrong, the clock is off), 403 means "you are who you say and
    still not allowed" (`jd teams add`). The sidecar logs them distinctly for the same reason, so
    `jd server logs -s auth-sidecar` can answer "why am I locked out". Collapsing the two sends the
    user to debug the wrong half of the system.
    """
    tampered = retarget_token(mint_token(deployment_id, aws_region), query={"X-Amz-Signature": "0" * 64})

    status, _ = _probe(connect_bundle, headers=auth_headers(tampered, deployment_id))
    assert status == 401, f"Expected 401 when STS refuses the replay, got {status}"


# --------------------------------------------------------------------------- TLS / cert pin


def test_direct_tls_without_pin_fails_verification(connect_bundle: dict) -> None:
    """The instance's cert does not chain to the system trust store.

    Which is exactly why the pin exists, and why it is transported out-of-band through SSM rather
    than being something a client can discover on the wire. A client that "just worked" against the
    system store would mean the cert was issued by a public CA — impossible for an IP-addressed
    instance with no domain.
    """
    with pytest.raises(ssl.SSLCertVerificationError):
        system_trust_request(connect_bundle["host"], connect_bundle["port"], AUTH_PROBE_PATH)


def test_direct_tls_without_token_is_rejected_401(connect_bundle: dict) -> None:
    """Reaching ``:443`` unverified but with no token -> 401. Auth is the boundary, not the network.

    The security group opens ``:443`` to the world by design, so anyone can complete a TLS handshake
    with the instance. This pins the consequence: reaching the door is not getting in. If it ever
    returned 200, the deployment would be world-readable.
    """
    status, _ = unverified_request(connect_bundle["host"], connect_bundle["port"], AUTH_PROBE_PATH)
    assert status == 401, f"Expected 401 when reaching :443 with no identity token, got {status}"


def test_served_cert_matches_cert_pin_ssm_parameter(connect_bundle: dict) -> None:
    """The cert the instance serves is byte-for-byte the PEM published to SSM.

    The pin's whole transport chain in one assertion: the instance generated a key, terraform
    published the PEM to SSM, and ``jd proxy connect-info`` read it back. Any break — a regenerated
    cert not re-published, a stale parameter — makes every proxy connection fail verification, and
    the only symptom a user sees is an opaque TLS error.
    """
    served = served_cert_pem(connect_bundle["host"], connect_bundle["port"])

    assert cert_fingerprint(served) == cert_fingerprint(connect_bundle["ca_cert"]), (
        "The cert served on :443 is not the PEM published to SSM; the pin cannot validate"
    )
