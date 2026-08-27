import unittest
from unittest.mock import Mock

from botocore.exceptions import ClientError

from jupyter_deploy.api.aws.ec2 import ec2_security_group


class TestReconcileCallerIngress(unittest.TestCase):
    def _client_with_existing(self, cidrs: list[str], port: int = 443) -> Mock:
        client = Mock()
        client.describe_security_groups.return_value = {
            "SecurityGroups": [
                {
                    "IpPermissions": [
                        {
                            "IpProtocol": "tcp",
                            "FromPort": port,
                            "ToPort": port,
                            "IpRanges": [{"CidrIp": c} for c in cidrs],
                        }
                    ]
                }
            ]
        }
        return client

    def test_authorizes_when_absent_and_revokes_stale(self) -> None:
        client = self._client_with_existing(["0.0.0.0/32", "198.51.100.9/32"])

        ec2_security_group.reconcile_caller_ingress(client, "sg-1", "203.0.113.7/32", port=443)

        client.authorize_security_group_ingress.assert_called_once()
        # Both stale cidrs revoked, the desired one kept.
        revoked = [
            call.kwargs["IpPermissions"][0]["IpRanges"][0]["CidrIp"]
            for call in client.revoke_security_group_ingress.call_args_list
        ]
        self.assertCountEqual(revoked, ["0.0.0.0/32", "198.51.100.9/32"])

    def test_no_authorize_when_already_present_no_stale(self) -> None:
        client = self._client_with_existing(["203.0.113.7/32"])

        ec2_security_group.reconcile_caller_ingress(client, "sg-1", "203.0.113.7/32", port=443)

        client.authorize_security_group_ingress.assert_not_called()
        client.revoke_security_group_ingress.assert_not_called()

    def test_revoke_permission_omits_description(self) -> None:
        # Revoke must match on CIDR only — a description would make AWS miss rules created
        # with a different one (e.g. the terraform placeholder).
        client = self._client_with_existing(["0.0.0.0/32"])

        ec2_security_group.reconcile_caller_ingress(client, "sg-1", "203.0.113.7/32", port=443)

        revoke_range = client.revoke_security_group_ingress.call_args.kwargs["IpPermissions"][0]["IpRanges"][0]
        self.assertNotIn("Description", revoke_range)

    def test_tolerates_duplicate_authorize(self) -> None:
        client = self._client_with_existing([])
        client.authorize_security_group_ingress.side_effect = ClientError(
            {"Error": {"Code": "InvalidPermission.Duplicate"}}, "AuthorizeSecurityGroupIngress"
        )

        # Should not raise.
        ec2_security_group.reconcile_caller_ingress(client, "sg-1", "203.0.113.7/32", port=443)

    def test_reraises_non_duplicate_authorize_error(self) -> None:
        client = self._client_with_existing([])
        client.authorize_security_group_ingress.side_effect = ClientError(
            {"Error": {"Code": "UnauthorizedOperation"}}, "AuthorizeSecurityGroupIngress"
        )

        with self.assertRaises(ClientError):
            ec2_security_group.reconcile_caller_ingress(client, "sg-1", "203.0.113.7/32", port=443)

    def test_reraises_describe_security_groups_error(self) -> None:
        client = Mock()
        client.describe_security_groups.side_effect = ClientError(
            {"Error": {"Code": "UnauthorizedOperation"}}, "DescribeSecurityGroups"
        )

        with self.assertRaises(ClientError):
            ec2_security_group.reconcile_caller_ingress(client, "sg-1", "203.0.113.7/32", port=443)

    def test_reraises_revoke_error(self) -> None:
        # A stale cidr is present, so reconcile authorizes the desired one then revokes the stale.
        client = self._client_with_existing(["0.0.0.0/32"])
        client.revoke_security_group_ingress.side_effect = ClientError(
            {"Error": {"Code": "UnauthorizedOperation"}}, "RevokeSecurityGroupIngress"
        )

        with self.assertRaises(ClientError):
            ec2_security_group.reconcile_caller_ingress(client, "sg-1", "203.0.113.7/32", port=443)
