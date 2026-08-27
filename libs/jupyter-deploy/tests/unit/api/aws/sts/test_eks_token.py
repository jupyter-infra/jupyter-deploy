import unittest
from unittest.mock import Mock, patch

from jupyter_deploy.api.aws.sts.eks_token import get_eks_bearer_token
from jupyter_deploy.exceptions import InvalidProviderCredentialsError


class TestGetEksBearerToken(unittest.TestCase):
    @patch("jupyter_deploy.api.aws.sts.eks_token.SigV4QueryAuth")
    @patch("jupyter_deploy.api.aws.sts.eks_token.BotocoreSession")
    def test_returns_prefixed_base64url_token(self, mock_session_cls: Mock, mock_signer_cls: Mock) -> None:
        mock_session: Mock = Mock()
        mock_session_cls.return_value = mock_session
        mock_creds: Mock = Mock()
        mock_session.get_credentials.return_value.get_frozen_credentials.return_value = mock_creds

        mock_signer: Mock = Mock()
        mock_signer_cls.return_value = mock_signer

        token = get_eks_bearer_token("my-cluster", "us-west-2")

        self.assertTrue(token.startswith("k8s-aws-v1."))
        mock_signer_cls.assert_called_once_with(mock_creds, "sts", "us-west-2", expires=60)
        mock_signer.add_auth.assert_called_once()

    @patch("jupyter_deploy.api.aws.sts.eks_token.SigV4QueryAuth")
    @patch("jupyter_deploy.api.aws.sts.eks_token.BotocoreSession")
    def test_uses_correct_sts_endpoint(self, mock_session_cls: Mock, mock_signer_cls: Mock) -> None:
        mock_session_cls.return_value = Mock()
        mock_signer_cls.return_value = Mock()

        get_eks_bearer_token("my-cluster", "eu-west-1")

        request_arg = mock_signer_cls.return_value.add_auth.call_args[0][0]
        self.assertIn("sts.eu-west-1.amazonaws.com", request_arg.url)
        self.assertEqual(request_arg.headers["x-k8s-aws-id"], "my-cluster")

    @patch("jupyter_deploy.api.aws.sts.eks_token.BotocoreSession")
    def test_raises_when_no_credentials_in_chain(self, mock_session_cls: Mock) -> None:
        mock_session: Mock = Mock()
        mock_session_cls.return_value = mock_session
        mock_session.get_credentials.return_value = None

        with self.assertRaises(InvalidProviderCredentialsError):
            get_eks_bearer_token("my-cluster", "us-west-2")

    @patch("jupyter_deploy.api.aws.sts.eks_token.SigV4QueryAuth")
    @patch("jupyter_deploy.api.aws.sts.eks_token.BotocoreSession")
    def test_binding_id_is_passed_as_x_k8s_aws_id_header(self, mock_session_cls: Mock, mock_signer_cls: Mock) -> None:
        # The `binding_id` param generalizes what EKS calls the cluster name: for the
        # jupyterlab template, the value is the deployment_id, and it must land in the
        # `x-k8s-aws-id` header so the STS presigned URL binds to this deployment.
        mock_session_cls.return_value = Mock()
        mock_signer_cls.return_value = Mock()

        get_eks_bearer_token(binding_id="deployment-abc-123", region="us-west-2")

        request_arg = mock_signer_cls.return_value.add_auth.call_args[0][0]
        self.assertEqual(request_arg.headers["x-k8s-aws-id"], "deployment-abc-123")

    @patch("jupyter_deploy.api.aws.sts.eks_token.SigV4QueryAuth")
    @patch("jupyter_deploy.api.aws.sts.eks_token.BotocoreSession")
    def test_expires_in_seconds_flows_to_signer(self, mock_session_cls: Mock, mock_signer_cls: Mock) -> None:
        mock_session_cls.return_value = Mock()
        mock_signer_cls.return_value = Mock()

        get_eks_bearer_token(binding_id="x", region="us-east-1", expires_in_seconds=900)

        mock_signer_cls.assert_called_once()
        _, kwargs = mock_signer_cls.call_args
        self.assertEqual(kwargs["expires"], 900)
