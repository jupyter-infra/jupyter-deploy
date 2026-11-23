"""Pin region handling in the local readiness-wait script that `jd up` runs."""

import re
import unittest

from jupyter_deploy_tf_aws_ec2_base.template import TEMPLATE_PATH

SCRIPT = TEMPLATE_PATH / "engine" / "local-await-server.sh.tftpl"


class TestAwaitServerScriptRegion(unittest.TestCase):
    def test_every_aws_call_passes_the_region(self) -> None:
        """Without --region, a call falls back to the user's default region, or fails when none is set.

        The script runs on the user's machine, where no default region is guaranteed; a call that
        fails here makes the wait loop misread the instance state.
        """
        # Join backslash-continued lines so each command is one logical line.
        text = re.sub(r"\\\n\s*", " ", SCRIPT.read_text())
        calls = [line for line in text.splitlines() if re.search(r"\baws (ec2|ssm) [a-z]", line)]
        self.assertTrue(calls, "found no aws calls; the script layout changed")
        missing = [call.strip() for call in calls if '--region "$REGION"' not in call]
        self.assertEqual(missing, [], "aws calls without --region")
