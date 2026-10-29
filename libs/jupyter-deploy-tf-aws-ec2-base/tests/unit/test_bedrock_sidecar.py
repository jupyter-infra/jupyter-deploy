"""Runs the Bedrock credential sidecar's refresh script against a fake ``aws`` CLI.

The script only meets the real STS and the jupyter container on a live instance; these tests pin
the two contracts it must honour there: the ``aws sts assume-role`` call it makes and the
``credential_process`` JSON it publishes.
"""

import filecmp
import json
import os
import shutil
import signal
import stat
import subprocess
import tempfile
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import botocore.session
from botocore.credentials import RefreshableCredentials

from jupyter_deploy_tf_aws_ec2_base.template import TEMPLATE_PATH

SIDECAR_PATH: Path = TEMPLATE_PATH / "services" / "bedrock-sidecar"
# Both EC2 templates ship the same sidecar; the sibling package is three levels above `template`.
TWIN_SIDECAR_PATH: Path = (
    TEMPLATE_PATH.parents[2]
    / "jupyter-deploy-tf-aws-ec2-jupyterlab"
    / "jupyter_deploy_tf_aws_ec2_jupyterlab"
    / "template"
    / "services"
    / "bedrock-sidecar"
)
ROLE_ARN = "arn:aws:iam::123456789012:role/bedrock-app"
FAKE_EXPIRATION = "2099-01-01T00:00:00+00:00"


def _gnu_date() -> str | None:
    """The script relies on GNU `date -d`; macOS ships BSD date, which only has it via coreutils."""
    for candidate in ("gdate", "date"):
        if shutil.which(candidate) and not subprocess.run([candidate, "-d", "@0"], capture_output=True).returncode:
            return candidate
    return None


GNU_DATE: str | None = _gnu_date()


class TestRefreshScript(unittest.TestCase):
    SCRIPT: Path = SIDECAR_PATH / "refresh.sh"

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.creds = self.tmp / "creds" / "credentials.json"
        self.creds.parent.mkdir()
        self.argv_log = self.tmp / "aws-argv.log"
        self.fail_flag = self.tmp / "FAIL"
        fake_bin = self.tmp / "bin"
        fake_bin.mkdir()
        (fake_bin / "aws").write_text(
            "#!/bin/sh\n"
            f'echo "$*" >> "{self.argv_log}"\n'
            f'[ -e "{self.fail_flag}" ] && exit 255\n'
            f"printf 'AKIAFAKE\\tSECRETFAKE\\tTOKENFAKE\\t{FAKE_EXPIRATION}\\n'\n"
        )
        (fake_bin / "aws").chmod(0o755)
        if GNU_DATE and GNU_DATE != "date":
            (fake_bin / "date").write_text(f'#!/bin/sh\nexec {GNU_DATE} "$@"\n')
            (fake_bin / "date").chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            "BEDROCK_APP_ROLE_ARN": ROLE_ARN,
            # Longer than any _run_loop: the kill lands in `sleep`, never between the .tmp write and the mv.
            "REFRESH_INTERVAL_S": "60",
            "CREDS_FILE": str(self.creds),
        }

    def _run_loop(self, seconds: float) -> tuple[bool, str]:
        """Run the loop for ``seconds`` then kill it; return (was still running, stderr)."""
        stderr = self.tmp / "stderr.log"
        with stderr.open("w") as err:
            # Own session so the kill also reaches the `sleep` the script forks.
            proc = subprocess.Popen(["sh", str(self.SCRIPT)], env=self.env, stderr=err, start_new_session=True)
            try:
                proc.wait(timeout=seconds)
                alive = False
            except subprocess.TimeoutExpired:
                alive = True
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
        return alive, stderr.read_text()

    def _healthcheck(self) -> int:
        return subprocess.run(["sh", str(self.SCRIPT), "-healthcheck"], env=self.env, capture_output=True).returncode

    def test_writes_credential_process_json_atomically(self) -> None:
        alive, stderr = self._run_loop(1.5)

        self.assertTrue(alive, f"loop exited early: {stderr}")
        self.assertEqual(
            json.loads(self.creds.read_text()),
            {
                "Version": 1,
                "AccessKeyId": "AKIAFAKE",
                "SecretAccessKey": "SECRETFAKE",
                "SessionToken": "TOKENFAKE",
                "Expiration": FAKE_EXPIRATION,
            },
        )
        self.assertEqual(stat.S_IMODE(self.creds.stat().st_mode), 0o444)
        self.assertEqual([p.name for p in self.creds.parent.iterdir()], [self.creds.name], "temp file left behind")

    def test_assume_role_arguments(self) -> None:
        self._run_loop(1.5)

        argv = self.argv_log.read_text().splitlines()[0].split()
        self.assertEqual(argv[:2], ["sts", "assume-role"])
        for flag, value in (
            ("--role-arn", ROLE_ARN),
            ("--role-session-name", "jupyter"),
            ("--duration-seconds", "3600"),
            ("--output", "text"),
        ):
            self.assertEqual(argv[argv.index(flag) + 1], value)
        self.assertEqual(
            argv[argv.index("--query") + 1], "Credentials.[AccessKeyId,SecretAccessKey,SessionToken,Expiration]"
        )

    def test_keeps_retrying_when_assume_role_fails(self) -> None:
        self.fail_flag.touch()

        alive, stderr = self._run_loop(1.5)

        self.assertTrue(alive, f"loop gave up: {stderr}")
        self.assertFalse(self.creds.exists())
        self.assertFalse(list(self.creds.parent.iterdir()), "temp file left behind")
        self.assertTrue(self.argv_log.exists(), "aws was never called")
        self.assertIn("assume-role", stderr)
        self.assertEqual(self._healthcheck(), 1, "healthcheck must fail with no credentials file")

    @unittest.skipUnless(GNU_DATE, "needs GNU date -d (install coreutils for gdate on macOS)")
    def test_healthcheck_requires_five_minute_margin(self) -> None:
        for ahead_s, expected in ((60, 1), (3600, 0)):
            with self.subTest(ahead_s=ahead_s):
                expiration = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(time.time() + ahead_s))
                self.creds.write_text(json.dumps({"Version": 1, "Expiration": expiration}))

                self.assertEqual(self._healthcheck(), expected)

    def test_missing_role_arn_is_fatal(self) -> None:
        del self.env["BEDROCK_APP_ROLE_ARN"]

        alive, stderr = self._run_loop(1.5)

        self.assertFalse(alive)
        self.assertIn("BEDROCK_APP_ROLE_ARN", stderr)
        self.assertFalse(self.argv_log.exists(), "aws must not be called without a role")


class TestSidecarImage(unittest.TestCase):
    def test_dockerfile_runs_the_script_on_the_aws_cli_image(self) -> None:
        instructions = [
            " ".join(line.split())
            for line in (SIDECAR_PATH / "Dockerfile").read_text().splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

        self.assertEqual(
            instructions,
            [
                "FROM public.ecr.aws/aws-cli/aws-cli:latest",
                "COPY refresh.sh /refresh.sh",
                "RUN chmod 755 /refresh.sh",
                'ENTRYPOINT ["/refresh.sh"]',
            ],
        )

    def test_script_is_executable(self) -> None:
        self.assertTrue(os.access(SIDECAR_PATH / "refresh.sh", os.X_OK))

    def test_copies_are_identical(self) -> None:
        for name in ("Dockerfile", "refresh.sh"):
            with self.subTest(file=name):
                self.assertTrue(filecmp.cmp(SIDECAR_PATH / name, TWIN_SIDECAR_PATH / name, shallow=False))


class TestSdkReadsPublishedCredentials(unittest.TestCase):
    """The sidecar's JSON, the template's ``aws-config`` and botocore meet here, with no network."""

    AWS_CONFIG: Path = TEMPLATE_PATH / "services" / "jupyter" / "aws-config"
    PUBLISHED_PATH = "/run/bedrock-creds/credentials.json"
    REMOVED_ENV = ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN", "AWS_PROFILE")

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.creds = self.tmp / "credentials.json"
        config_text = self.AWS_CONFIG.read_text()
        self.assertIn(self.PUBLISHED_PATH, config_text)
        config = self.tmp / "config"
        config.write_text(config_text.replace(self.PUBLISHED_PATH, str(self.creds)))
        # A developer's own credentials must never satisfy the chain in this test.
        env = {k: v for k, v in os.environ.items() if k not in self.REMOVED_ENV}
        env.update(
            AWS_CONFIG_FILE=str(config),
            AWS_SHARED_CREDENTIALS_FILE=str(self.tmp / "no-such-file"),
            AWS_EC2_METADATA_DISABLED="true",
        )
        patcher = patch.dict(os.environ, env, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _publish(self, access_key_id: str, expiration: datetime) -> None:
        # The printf shape of refresh.sh.
        self.creds.write_text(
            f'{{"Version": 1, "AccessKeyId": "{access_key_id}", "SecretAccessKey": "SECRETFAKE", '
            f'"SessionToken": "TOKENFAKE", "Expiration": "{expiration.isoformat()}"}}\n'
        )

    def test_credentials_are_refreshable_and_reread_before_expiry(self) -> None:
        first_expiry = datetime.now(UTC).replace(microsecond=0) + timedelta(hours=1)
        self._publish("ASIAOLD", first_expiry)

        creds = botocore.session.Session().get_credentials()

        assert isinstance(creds, RefreshableCredentials), creds
        self.assertEqual(creds.method, "custom-process")
        self.assertEqual(creds.access_key, "ASIAOLD")
        # botocore exposes the expiry only through this attribute.
        self.assertEqual(creds._expiry_time, first_expiry)

        # The sidecar rotates while the SDK session lives on: the file is re-read inside botocore's
        # advisory refresh window, which keeps a long-lived kernel or agent working across rotations.
        second_expiry = first_expiry + timedelta(minutes=15)
        self._publish("ASIANEW", second_expiry)
        creds._expiry_time = datetime.now(UTC) + timedelta(seconds=60)
        self.assertEqual(creds.get_frozen_credentials().access_key, "ASIANEW")
        self.assertEqual(creds._expiry_time, second_expiry)
