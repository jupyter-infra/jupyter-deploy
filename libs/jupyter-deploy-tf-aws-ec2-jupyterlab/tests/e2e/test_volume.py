"""E2E tests for `jd volume` against the home volume — non-mutating.

Everything here operates on the volume the template always creates, and reaches it WITHOUT --name:
the default is the first entry of the manifest's ``volumes.static`` list, and asserting that the
default resolves to the home volume is a large part of the point. A user inspecting their notebook
storage should not have to know an identity to do it.

Commands are issued inline rather than through local helpers, so each test reads as the thing it is
testing. The two plugin helpers (``get_volume_names`` / ``get_volume_details``) appear only where a
volume's state is a *precondition* — never in the `list` and `show` tests themselves, which would
otherwise assert that a helper agrees with itself.

Non-mutating in the sense the suite means it: no `jd config`, no `jd up`, no instance replacement.
``test_volume_backup_*`` does create a real EBS snapshot and needs a stopped host, which is a cloud
side effect but not a change to the deployment — and only ever one snapshot, since each backup
supersedes the previous one. The destroy-time reaper removes the last one.

Deliberately elsewhere:
  - the additional EBS/EFS mounts, and the zone swap they exist to protect, need a `jd up` to
    provision — see ``test_volume_swaps.py``.
  - file-system semantics of the home volume itself are ``test_home_volume.py``.
"""

import json

import pytest
from pytest_jupyter_deploy.cli import JDCliError
from pytest_jupyter_deploy.deployment import EndToEndDeployment
from pytest_jupyter_deploy.volumes import get_volume_details

from .constants import HOME_VOLUME


def _assert_clean_failure(excinfo: pytest.ExceptionInfo[JDCliError], expected: str) -> None:
    """Assert the CLI failed with `expected` in its output and no Python traceback.

    A traceback means the error escaped the CLI's error handling: the user sees an internal stack
    instead of a message they can act on, which is a defect regardless of the exit code being right.
    """
    message = " ".join(str(excinfo.value).split())
    assert expected in message, f"Expected {expected!r} in the failure, got: {message}"
    for leak in ("Traceback (most recent call last)", 'File "/workspace'):
        assert leak not in message, f"The CLI leaked a stack trace:\n{message}"


def test_volume_list_json_reports_name_class_and_description(e2e_deployment: EndToEndDeployment) -> None:
    """`jd volume list --json` emits `{name, class, description}` per volume, like `component list`.

    Two things only a live deployment can show. The identity is the mount path rather than the provider
    id — an id would be useless as input to `show`/`backup`, which is what every other command takes.
    And `class` carries the real manifest value, so the field a reader uses to tell a backup-able volume
    from one that is not is populated end to end rather than defaulted to "".
    """
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "volume", "list", "--json"])
    volumes = json.loads(result.stdout)

    by_name = {volume["name"]: volume for volume in volumes}
    assert HOME_VOLUME in by_name, f"Expected '{HOME_VOLUME}' among the listed volumes, got {list(by_name)}"
    assert by_name[HOME_VOLUME]["volume_class"] == "ebs", f"Unexpected storage class: {by_name[HOME_VOLUME]}"
    assert by_name[HOME_VOLUME]["description"], "Every volume the template declares carries a description"
    assert not any(name.startswith("vol-") for name in by_name), (
        f"Volumes are listed by provider id rather than identity: {list(by_name)}"
    )


def test_volume_list_renders_a_table(e2e_deployment: EndToEndDeployment) -> None:
    """The default rendering is a Name / Class / Description table, shaped like `jd component list`.

    The `Class` column is the reason it is a table rather than a list of names: `ebs` versus `efs` is
    what decides whether a volume can be backed up at all, so a bare list would hide the most
    consequential difference between two rows. Headed `Class` and not `Type` because a volume also has a
    provider-assigned volume type (`gp3`), which `show` reports separately.
    """
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "volume", "list"])
    output = e2e_deployment.cli.strip_ansi(result.stdout)

    for expected in ("Name", "Class", "Description", HOME_VOLUME, "ebs"):
        assert expected in output, f"Expected {expected!r} in the table:\n{output}"


def test_volume_list_text_output_is_names_only(e2e_deployment: EndToEndDeployment) -> None:
    """`--text` gives comma-separated names, for a caller piping into another command.

    Asserted to carry NO table chrome: `--text` exists so a script does not have to parse a rendering
    that is free to change, and a header leaking into it would break exactly that caller.
    """
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "volume", "list", "--text"])
    output = e2e_deployment.cli.strip_ansi(result.stdout).strip()

    assert HOME_VOLUME in output.split(","), f"Expected '{HOME_VOLUME}' among the names, got {output!r}"
    for chrome in ("Name", "Class", "Description", "─"):
        assert chrome not in output, f"--text leaked table rendering: {output!r}"


def test_volume_list_rejects_json_and_text_together(e2e_deployment: EndToEndDeployment) -> None:
    """The two output modes are mutually exclusive, and asking for both is a clean error."""
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError) as excinfo:
        e2e_deployment.cli.run_command(["jupyter-deploy", "volume", "list", "--json", "--text"])

    _assert_clean_failure(excinfo, "Cannot use both")


def test_volume_show_defaults_to_the_home_volume(e2e_deployment: EndToEndDeployment) -> None:
    """Bare `jd volume show` resolves to the home volume and reports its live state.

    The manifest declares `home` first in `volumes.static`, and that ordering IS the default-name
    contract. Also the join this command exists for: the identity and mount point come from the
    manifest, while the zone, capacity and type come from a live provider call — a `show` that
    returned only the declaration would look identical here right up until a volume went missing.
    """
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "volume", "show", "--json"])
    detail = json.loads(result.stdout)

    assert detail["name"] == HOME_VOLUME
    assert detail["mount_point"] == "/home/jovyan", f"Unexpected mount point: {detail['mount_point']}"
    assert detail["volume_id"].startswith("vol-"), f"Expected an EBS volume id, got {detail['volume_id']}"

    # Live fields: present because the project is applied. A configured-but-unapplied volume reports
    # these empty, which is why their absence here would be a real failure rather than a shrug.
    assert detail["zone"], "Expected a live availability zone for an applied volume"
    assert detail["capacity"].endswith("Gi"), f"Expected a provisioned capacity quantity, got {detail['capacity']}"
    assert detail["encrypted"] is True, "The home volume must be encrypted"

    # The class is declared and the tier is live, so both must be present and must not be the same field:
    # `gp3` alone says nothing about which storage service answered.
    assert detail["volume_class"] == "ebs", f"Unexpected storage class: {detail['volume_class']!r}"
    assert detail["volume_type"] == "gp3", f"Unexpected provider tier: {detail['volume_type']!r}"


def test_volume_show_by_name_matches_the_default(e2e_deployment: EndToEndDeployment) -> None:
    """`--name home` and no --name describe the same volume.

    Asserted as an equality rather than by re-checking fields: this is the property that makes the
    default safe to rely on, and it would break silently if the default ever came from somewhere
    other than the manifest (a hardcoded string, the first volume the provider happens to return).
    """
    e2e_deployment.ensure_deployed()

    explicit = e2e_deployment.cli.run_command(["jupyter-deploy", "volume", "show", "--name", HOME_VOLUME, "--json"])
    default = e2e_deployment.cli.run_command(["jupyter-deploy", "volume", "show", "--json"])

    assert json.loads(explicit.stdout) == json.loads(default.stdout), (
        f"--name {HOME_VOLUME} and the default disagree:\n{explicit.stdout}\n{default.stdout}"
    )


def test_volume_status_defaults_to_the_home_volume(e2e_deployment: EndToEndDeployment) -> None:
    """`jd volume status` reports one status, for one volume: the home volume's attachment state.

    A detached data volume means the app has no notebooks, which `jd host status` alone would not
    reveal — and `attached` is a live fact, so the whole read path has to work to produce it.

    The status is the volume's own condition and nothing else. Backup freshness is a property of the
    BACKUP, and lives in `show` as `backup_state` / `backup_timestamp`; folding it in here would make
    one status line mean two things that can disagree.
    """
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "volume", "status"])
    status = e2e_deployment.cli.strip_ansi(result.stdout)

    assert "Volume status: attached" in status, f"Expected the home volume to be attached, got: {status}"
    assert status.count("status:") == 1, f"Expected exactly one status line, got: {status}"
    assert "backed up" not in status, f"Status must describe the volume, not its backup: {status}"


def test_volume_status_accepts_an_explicit_name(e2e_deployment: EndToEndDeployment) -> None:
    """`--name home` names the same volume the default resolves to, so it reports the same status."""
    e2e_deployment.ensure_deployed()

    result = e2e_deployment.cli.run_command(["jupyter-deploy", "volume", "status", "--name", HOME_VOLUME])
    status = e2e_deployment.cli.strip_ansi(result.stdout)

    assert "Volume status: attached" in status, f"Unexpected status for '{HOME_VOLUME}': {status}"
    assert status.count("status:") == 1, f"Expected exactly one status line, got: {status}"


def test_volume_backup_refuses_while_the_host_runs(e2e_deployment: EndToEndDeployment) -> None:
    """A backup of a live disk is refused, not taken with a warning.

    Declared BEFORE the tests that use `stopped_host`, deliberately: a module-scoped fixture is set up
    on first request, so this is the only place in the file where a running host is still guaranteed.

    Cheap enough to stay `cli`-marked — the gate is the first step of the sequence, so it fails before
    any snapshot is created.
    """
    e2e_deployment.ensure_server_running()

    with pytest.raises(JDCliError) as excinfo:
        e2e_deployment.cli.run_command(["jupyter-deploy", "volume", "backup"])

    _assert_clean_failure(excinfo, "must be stopped")
    assert "jd host stop" in " ".join(str(excinfo.value).split()), "The refusal must say how to proceed"


def test_volume_backup_defaults_to_the_home_volume(
    e2e_deployment: EndToEndDeployment,
    stopped_host: None,
) -> None:
    """Bare `jd volume backup` backs up the home volume, and `show` then reports it.

    One command, three things asserted, because they are only meaningful together: the backup is
    created, it is discoverable afterwards through the SAME identity that was never typed, and it
    reports `completed` — an incomplete snapshot cannot seed a volume, so a backup that returned
    while still pending would be a backup that cannot be restored.

    Not `cli`-marked, unlike the read-only tests above: it needs a stopped host, and a ~4-minute
    stop/start cycle does not belong in the fast release-validation pass.
    """
    result = e2e_deployment.cli.run_command(["jupyter-deploy", "volume", "backup"], timeout_seconds=1800)
    assert HOME_VOLUME in e2e_deployment.cli.strip_ansi(result.stdout)

    detail = get_volume_details(e2e_deployment)
    assert detail["backup_id"].startswith("snap-"), f"Expected a snapshot id, got {detail['backup_id']!r}"
    assert detail["backup_state"] == "completed", (
        f"A backup that is not 'completed' cannot seed a volume: {detail['backup_state']!r}"
    )
    assert detail["backup_timestamp"], "Expected a backup timestamp, so a reader can tell how stale it is"


def test_volume_backup_replaces_the_previous_backup(
    e2e_deployment: EndToEndDeployment,
    stopped_host: None,
) -> None:
    """A second backup supersedes the first, leaving exactly one.

    "Only one backup per volume" is a deliberate design choice, not an accident of the API, so it is
    pinned: the new snapshot id must differ. The ordering that makes this safe (delete only AFTER the
    replacement completes) is unit-tested; what E2E adds is that the delete has PERMISSION to happen.
    """
    e2e_deployment.cli.run_command(["jupyter-deploy", "volume", "backup"], timeout_seconds=1800)
    first = get_volume_details(e2e_deployment)["backup_id"]
    assert first, "Expected the first backup to be recorded"

    e2e_deployment.cli.run_command(["jupyter-deploy", "volume", "backup"], timeout_seconds=1800)
    second = get_volume_details(e2e_deployment)["backup_id"]

    assert second and second != first, f"Expected a new backup to supersede {first}, got {second!r}"


def test_volume_show_rejects_an_unknown_name(e2e_deployment: EndToEndDeployment) -> None:
    """An identity this deployment does not mount is a clean error, not an empty result.

    Empty output would read as "you have no volumes" — the opposite of the truth, and the kind of
    answer that sends someone looking for a broken deployment instead of a typo.
    """
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError) as excinfo:
        e2e_deployment.cli.run_command(["jupyter-deploy", "volume", "show", "--name", "invalid", "--json"])

    _assert_clean_failure(excinfo, "invalid")

    # The refusal names what IS mounted, plus the command that lists it. Asserted here because only the
    # error decorator renders that, so a handler raising the wrong exception class still exits 1 with a
    # clean message — the regression is invisible to any test that only checks the failure happened.
    message = " ".join(str(excinfo.value).split())
    assert HOME_VOLUME in message, f"The refusal must name the volumes that ARE mounted: {message}"
    assert "jd volume list" in message, f"The refusal must say how to find the right name: {message}"


def test_volume_status_rejects_an_unknown_name(e2e_deployment: EndToEndDeployment) -> None:
    """`status --name invalid` fails rather than reporting every volume.

    Worth its own test: bare `status` legitimately covers all volumes, so a lookup that quietly fell
    back to that behavior would look like success and hide the typo.
    """
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError) as excinfo:
        e2e_deployment.cli.run_command(["jupyter-deploy", "volume", "status", "--name", "invalid"])

    _assert_clean_failure(excinfo, "invalid")


def test_volume_backup_rejects_an_unknown_name(e2e_deployment: EndToEndDeployment) -> None:
    """`backup --name invalid` fails before creating anything.

    The failure must come from the lookup, not from the provider: a command that resolved `invalid`
    to the default volume would silently back up the wrong thing and report success.
    """
    e2e_deployment.ensure_deployed()

    with pytest.raises(JDCliError) as excinfo:
        e2e_deployment.cli.run_command(["jupyter-deploy", "volume", "backup", "--name", "invalid"])

    _assert_clean_failure(excinfo, "invalid")
