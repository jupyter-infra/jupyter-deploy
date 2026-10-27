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
from pathlib import Path

from jupyter_deploy_tf_aws_ec2_jupyterlab.template import TEMPLATE_PATH

SIDECAR_PATH: Path = TEMPLATE_PATH / "services" / "bedrock-sidecar"
# Both EC2 templates ship the same sidecar; the sibling package is three levels above `template`.
TWIN_SIDECAR_PATH: Path = (
    TEMPLATE_PATH.parents[2]
    / "jupyter-deploy-tf-aws-ec2-base"
    / "jupyter_deploy_tf_aws_ec2_base"
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
            "REFRESH_INTERVAL_S": "1",
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
