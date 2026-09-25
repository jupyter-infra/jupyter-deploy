"""Apply #3 of the mutating pass: the allowlist reaches the instance through the VARIABLES (#367).

The existing `jd users` / `jd teams` tests cover the *command -> variable* direction: running
`jd users add alice` must write `alice` back into ``oauth_allowed_usernames`` so the next apply does
not revert it. This file covers the **reverse** direction, which nothing tested before: edit the
variable, run `jd config && jd up`, and the running allowlist must reconcile.

That direction used to be broken in two separate ways, and both are pinned here:

1. **It did not apply at all.** cloud-init seeded ``/etc/AUTHED_ENTITIES`` behind an
   ``if [ ! -f ]`` first-boot guard, so on an existing instance the file was already there and the
   new value was simply ignored. `jd up` reported success and changed nothing.
2. **It restarted everything.** The allowlist was interpolated into the startup document, so
   changing it changed that document's hash, which replaced the SSM association and re-ran the whole
   boot path -- ``docker compose up --force-recreate``, every container, every kernel killed. Paying
   a full app restart to edit a list of names.

``test_only_the_auth_container_restarts`` is the one that would fail against a naive fix (one that
simply re-seeds the file from cloud-init on every run): that fix is correct on (1) and still wrong
on (2).

3. **It applied the sections in a fixed order.** The reconcile writes one section per SSM call, and
   ``update-auth.sh`` refuses any single call that would leave no users and no org. A fixed order
   therefore fails one direction of change or the other, whichever empties a section first -- so both
   directions are pinned, one per branch of the ordering split:
   ``test_swapping_org_auth_for_user_auth_in_one_apply`` (org cleared: users, teams, org) and
   ``test_swapping_user_auth_for_org_auth_in_one_apply`` (org set: org, teams, users).

Uses ``safe_user`` as the probe rather than the logged-in user: granting and revoking access for
somebody who is not driving the browser cannot lock the suite out of its own deployment.
"""

import pytest
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.plugin import skip_if_testvars_not_set

from .constants import ORDER_MUTATING_AUTH_VARIABLES

# Every test here edits the live allowlist, so the snapshot/restore net is mandatory: a failure
# between the grant and the revoke would leave the probe user allowlisted for every later test.
pytestmark = pytest.mark.usefixtures("restore_allowlist")


def _container_started_at(e2e_deployment: EndToEndDeployment, container: str) -> str:
    """Return a container's Docker ``StartedAt`` timestamp, read on the host.

    `jd host exec` rather than `jd server exec`: the question is when the container was (re)started,
    which is a fact about the docker daemon on the host, not something visible from inside it.
    """
    result = e2e_deployment.cli.run_command(
        [
            "jupyter-deploy",
            "host",
            "exec",
            "--",
            "docker",
            "inspect",
            "-f",
            "{{.State.StartedAt}}",
            container,
        ]
    )
    started_at = result.stdout.strip()
    assert started_at, f"Could not read the start time of the {container} container: {result.stdout!r}"
    return started_at


@pytest.mark.order(ORDER_MUTATING_AUTH_VARIABLES)
@pytest.mark.mutating
@skip_if_testvars_not_set(["JD_E2E_SAFE_USER"])
def test_adding_a_user_to_the_variable_reaches_the_instance(
    e2e_deployment: EndToEndDeployment,
    logged_user: str,
    safe_user: str,
) -> None:
    """A user added to ``oauth_allowed_usernames`` is live after `jd up`.

    The regression test for the first-boot guard: before #367 this apply succeeded and the instance
    kept serving the old allowlist, so `jd users list` would not show the probe user and the next
    `jd up` would keep pretending it had applied the change.
    """
    e2e_deployment.ensure_server_running()

    live_before = [name.lower() for name in e2e_deployment.get_allowlisted_users()]
    assert safe_user.lower() not in live_before, (
        f"Probe user {safe_user!r} is already allowlisted, so this test would assert nothing. "
        "Pick a JD_E2E_SAFE_USER that is not in oauth_allowed_usernames."
    )

    e2e_deployment.ensure_deployed_with(
        [
            "--oauth-allowed-usernames",
            logged_user,
            "--oauth-allowed-usernames",
            safe_user,
        ]
    )

    in_variable = [name.lower() for name in e2e_deployment.get_list_str_variable_value("oauth_allowed_usernames")]
    assert safe_user.lower() in in_variable, "jd config did not record the probe user in oauth_allowed_usernames"

    live_after = [name.lower() for name in e2e_deployment.get_allowlisted_users()]
    assert safe_user.lower() in live_after, (
        f"{safe_user!r} is in oauth_allowed_usernames but not in the allowlist on the instance "
        f"({live_after}). The variable change did not reconcile -- `jd up` reported success and "
        "changed nothing on the host."
    )
    # The logged-in user must still be there: the reconcile uses `set`, so a bug that dropped the
    # rest of the list while adding the probe would lock the suite out of its own deployment.
    assert logged_user.lower() in live_after, f"The logged user fell off the allowlist: {live_after}"


@pytest.mark.order(ORDER_MUTATING_AUTH_VARIABLES + 1)
@pytest.mark.mutating
@skip_if_testvars_not_set(["JD_E2E_SAFE_USER"])
def test_only_the_auth_container_restarts(
    e2e_deployment: EndToEndDeployment,
    logged_user: str,
    safe_user: str,
) -> None:
    """An allowlist-only apply recreates the auth container and leaves the app alone.

    This is the half of #367 that makes it worth doing, and the half a naive fix fails. The app
    container holds the user's running kernels; recreating it to change a list of names loses work
    the user never agreed to lose. The oauth container, by contrast, must restart -- that is how the
    new allowlist reaches oauth2-proxy's environment.
    """
    e2e_deployment.ensure_server_running()

    jupyter_started_before = _container_started_at(e2e_deployment, "jupyter")
    oauth_started_before = _container_started_at(e2e_deployment, "oauth")

    # Revoke the probe user granted by the previous test: an allowlist-only change, nothing else.
    e2e_deployment.ensure_deployed_with(["--oauth-allowed-usernames", logged_user])

    e2e_deployment.ensure_server_running()

    assert _container_started_at(e2e_deployment, "jupyter") == jupyter_started_before, (
        "The jupyter container was restarted by an allowlist-only apply. Every running kernel just "
        "died to edit a list of names -- the allowlist has leaked back into the startup document, or "
        "the reconcile is recreating the whole compose stack instead of only the auth container."
    )
    assert _container_started_at(e2e_deployment, "oauth") != oauth_started_before, (
        "The oauth container was NOT restarted, so oauth2-proxy is still running with the old "
        "allowlist in its environment even though the file on disk changed."
    )

    live_after = [name.lower() for name in e2e_deployment.get_allowlisted_users()]
    assert safe_user.lower() not in live_after, (
        f"{safe_user!r} was removed from oauth_allowed_usernames but is still allowlisted on the "
        f"instance ({live_after}). The reconcile must apply `set` semantics, not `add`: a name "
        "dropped from the variable has to be revoked, or the variables are not the source of truth."
    )


@pytest.mark.order(ORDER_MUTATING_AUTH_VARIABLES + 2)
@pytest.mark.mutating
def test_an_unchanged_allowlist_restarts_nothing(
    e2e_deployment: EndToEndDeployment,
    logged_user: str,
) -> None:
    """Re-applying the same allowlist is a no-op, not a restart.

    Idempotence matters because `jd up` is the routine way to apply *any* change: if a no-op
    allowlist reconcile bounced the auth container, every unrelated apply would drop every live
    session for no reason.
    """
    e2e_deployment.ensure_server_running()

    jupyter_started_before = _container_started_at(e2e_deployment, "jupyter")
    oauth_started_before = _container_started_at(e2e_deployment, "oauth")

    # Exactly the allowlist the previous test left in place.
    e2e_deployment.ensure_deployed_with(["--oauth-allowed-usernames", logged_user])

    e2e_deployment.ensure_server_running()

    assert _container_started_at(e2e_deployment, "jupyter") == jupyter_started_before, (
        "An apply with no allowlist change restarted the jupyter container"
    )
    assert _container_started_at(e2e_deployment, "oauth") == oauth_started_before, (
        "An apply with no allowlist change restarted the oauth container; the reconcile is firing "
        "on every apply rather than only when the values differ"
    )


@pytest.mark.order(ORDER_MUTATING_AUTH_VARIABLES + 3)
@pytest.mark.mutating
@skip_if_testvars_not_set(["JD_E2E_ORG", "JD_E2E_SAFE_TEAM"])
def test_team_variable_changes_reach_the_instance(
    e2e_deployment: EndToEndDeployment,
    logged_org: str,
    safe_team: str,
) -> None:
    """``oauth_allowed_teams`` reconciles the same way the user list does.

    Teams live in a different section of ``/etc/AUTHED_ENTITIES`` and are written by a different
    branch of ``update-auth.sh``, so the users result does not imply this one.

    Only the grant direction is asserted, not clear-to-empty: no `jd config` flag can set a list
    variable back to empty (repeating the flag replaces the list; omitting it leaves it untouched),
    so the empty case is not reachable through the interface a user actually has. The
    ``update-auth.sh <section> set`` path that handles it is covered at the script level instead.

    No browser assertion: a team narrows an org grant, and the suite's own access comes from the
    user allowlist, so the interesting fact here is purely that the value propagated.
    """
    e2e_deployment.ensure_server_running()

    live_before = [team.lower() for team in e2e_deployment.get_allowlisted_teams()]
    assert safe_team.lower() not in live_before, (
        f"Probe team {safe_team!r} is already allowlisted, so this test would assert nothing. "
        "Pick a JD_E2E_SAFE_TEAM that is not in oauth_allowed_teams."
    )

    e2e_deployment.ensure_deployed_with(
        [
            "--oauth-allowed-org",
            logged_org,
            "--oauth-allowed-teams",
            safe_team,
        ]
    )
    live_teams = [team.lower() for team in e2e_deployment.get_allowlisted_teams()]
    assert safe_team.lower() in live_teams, (
        f"{safe_team!r} is in oauth_allowed_teams but not on the instance ({live_teams}). "
        "The teams section of the allowlist did not reconcile."
    )


@pytest.mark.order(ORDER_MUTATING_AUTH_VARIABLES + 4)
@pytest.mark.mutating
@skip_if_testvars_not_set(["JD_E2E_ORG", "JD_E2E_USER"])
def test_swapping_org_auth_for_user_auth_in_one_apply(
    e2e_deployment: EndToEndDeployment,
    logged_org: str,
    logged_user: str,
) -> None:
    """Dropping the org and adding the users in ONE apply reconciles, instead of refusing.

    The reconcile drives ``update-auth.sh`` once per section, and the script refuses any single
    operation that would leave the file with no users AND no org. It judges that on the file as it
    stands, so the section being emptied has to be written after the section being filled -- which
    means the order has to depend on the direction of the change, not be fixed.

    This is the transition that exposes it: from org-only auth to user-only auth, an `org remove`
    applied before `users set` sees an empty user list and fails the whole apply, even though the
    end state is one the plan accepted.

    Driven through ``variables.yaml`` rather than `jd config` flags because neither edit is
    expressible as one: a list cannot be emptied by repeating its flag, and `--oauth-allowed-org ""`
    does not round-trip (it reaches the tfvars as an escaped, ANSI-contaminated literal that fails
    the plan). The reverse direction is covered by the tests above, which end on an org plus a
    non-empty user list.
    """
    e2e_deployment.ensure_server_running()

    # Get to org-only auth: the org carries access, the user list is empty. Safe for the suite's own
    # access because the browser user is a member of this org. Both edits go in one apply, which the
    # reconcile handles in the `org set` order -- org first, so the empty `users set` has an org
    # behind it.
    e2e_deployment.update_required_value("oauth_allowed_org", logged_org)
    e2e_deployment.update_required_value("oauth_allowed_usernames", [])
    # `ensure_deployed_with([])` rather than `ensure_deployed()`: the latter short-circuits on an
    # already-deployed project, so it would never apply the values just written.
    e2e_deployment.ensure_deployed_with([])

    assert e2e_deployment.get_allowlisted_org() == logged_org, (
        "Setup did not reach org-only auth; the swap below would not be testing the failing order"
    )
    assert not e2e_deployment.get_allowlisted_users(), (
        f"Expected no allowlisted users before the swap, got {e2e_deployment.get_allowlisted_users()}"
    )

    # The swap, in one apply: org cleared and users filled together. The teams list has to go with
    # the org -- `local.teams_have_org` refuses a plan that keeps teams without one, and a previous
    # test in this module may have left one allowlisted.
    e2e_deployment.update_required_value("oauth_allowed_org", "")
    e2e_deployment.update_required_value("oauth_allowed_teams", [])
    e2e_deployment.update_required_value("oauth_allowed_usernames", [logged_user])
    e2e_deployment.ensure_deployed_with([])

    live_users = [name.lower() for name in e2e_deployment.get_allowlisted_users()]
    assert logged_user.lower() in live_users, (
        f"{logged_user!r} is in oauth_allowed_usernames but not on the instance ({live_users})"
    )
    assert not e2e_deployment.get_allowlisted_org(), (
        f"The org should have been cleared, but is still {e2e_deployment.get_allowlisted_org()!r}"
    )


@pytest.mark.order(ORDER_MUTATING_AUTH_VARIABLES + 5)
@pytest.mark.mutating
@skip_if_testvars_not_set(["JD_E2E_ORG", "JD_E2E_USER"])
def test_swapping_user_auth_for_org_auth_in_one_apply(
    e2e_deployment: EndToEndDeployment,
    logged_org: str,
    logged_user: str,
) -> None:
    """Adding the org and dropping the users in ONE apply reconciles, instead of refusing.

    The mirror of ``test_swapping_org_auth_for_user_auth_in_one_apply``, and the other half of the
    ordering fix: the reconcile's section order is chosen per direction, so each branch of the
    ``local.allowed_github_org != ""`` split needs its own test. This one drives the `org set` branch,
    which writes org, then teams, then users -- the trailing empty `users set` is only accepted
    because the org landed first. Ordering this branch users-first (the order the other direction
    needs) would hand ``update-auth.sh`` an empty user list with no org yet in the file, which it
    refuses, failing an apply whose end state the plan had accepted.

    Driven through ``variables.yaml`` for the same reason as its mirror: emptying
    ``oauth_allowed_usernames`` is not expressible as a `jd config` flag, since repeating a list flag
    replaces the list and omitting it leaves it untouched.
    """
    e2e_deployment.ensure_server_running()

    # Get to user-only auth. Already where the preceding test leaves the deployment, so this is a
    # no-op reconcile in a full-suite run -- stated explicitly so the test also holds when selected
    # on its own.
    e2e_deployment.update_required_value("oauth_allowed_usernames", [logged_user])
    e2e_deployment.update_required_value("oauth_allowed_org", "")
    e2e_deployment.update_required_value("oauth_allowed_teams", [])
    e2e_deployment.ensure_deployed_with([])

    live_before = [name.lower() for name in e2e_deployment.get_allowlisted_users()]
    assert logged_user.lower() in live_before, (
        f"Setup did not reach user-only auth ({live_before}); the swap below would not be testing the failing order"
    )
    assert not e2e_deployment.get_allowlisted_org(), (
        f"Expected no allowlisted org before the swap, got {e2e_deployment.get_allowlisted_org()!r}"
    )

    # The swap, in one apply: org filled and users emptied together. Safe for the suite's own access
    # because the browser user is a member of this org -- which is the whole point of the end state.
    e2e_deployment.update_required_value("oauth_allowed_org", logged_org)
    e2e_deployment.update_required_value("oauth_allowed_usernames", [])
    e2e_deployment.ensure_deployed_with([])

    assert e2e_deployment.get_allowlisted_org() == logged_org, (
        f"{logged_org!r} is in oauth_allowed_org but not on the instance ({e2e_deployment.get_allowlisted_org()!r})"
    )
    assert not e2e_deployment.get_allowlisted_users(), (
        f"The user list should have been emptied, but is still {e2e_deployment.get_allowlisted_users()}. "
        "The reconcile must apply `set` semantics to a cleared variable, not skip the empty write."
    )

    # Hand the module back with access resting on the user allowlist again. `restore_allowlist` only
    # repairs the FILE and deliberately leaves the variables as the test left them, so stopping here
    # would leave the next module's `jd up` reconciling straight back to org-only -- dropping the
    # logged user the teardown had just re-granted.
    e2e_deployment.update_required_value("oauth_allowed_usernames", [logged_user])
    e2e_deployment.update_required_value("oauth_allowed_org", "")
    e2e_deployment.update_required_value("oauth_allowed_teams", [])
    e2e_deployment.ensure_deployed_with([])

    live_after = [name.lower() for name in e2e_deployment.get_allowlisted_users()]
    assert logged_user.lower() in live_after, (
        f"Failed to restore the user allowlist after the swap ({live_after}); the suite's own access "
        "is left resting on org membership"
    )
