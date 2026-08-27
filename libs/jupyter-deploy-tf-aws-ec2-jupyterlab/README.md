# Jupyter Deploy AWS EC2 JupyterLab template

Terraform template that runs a **single-user JupyterLab** on a remote AWS EC2 instance,
reached from your laptop through the local `jupyter-deploy-client-proxy` over a pinned
self-signed TLS connection, authenticated with short-lived AWS-identity (STS) tokens.

**AWS credentials are the only prerequisite**.

```
jd init . -E terraform -P aws -I ec2 -T jupyterlab   # default template = aws:ec2:jupyterlab
jd config                                            # region, instance type, volume size
jd up                                                # provision instance + self-signed cert
jd open                                              # start the proxy and open the browser
```

## How it works

- **Data path:** the browser talks to a local proxy over `http://localhost`; the proxy
  talks to the instance's Traefik on `:443` over pinned self-signed TLS (the pin is on the
  cert, not the address, so a new public IP after a stop/start is a non-event).
- **Cert pin:** the instance generates a long-lived self-signed cert at boot (private key
  persisted on the EBS data volume) and publishes only the public PEM to an SSM parameter
  that `jd proxy connect-info` reads live.
- **Auth:** `jd proxy connect-info` mints a `k8s-aws-v1` STS-identity token; a ForwardAuth
  sidecar behind Traefik validates it (STS replay + ARN allowlist + `x-k8s-aws-id` binding).
  No shared secret is stored anywhere.
- **Network:** the security group allows `:443` only, reconciled to the caller's `/32` on
  every `jd open`.

## New IAM permissions

The *local* CLI credentials need, in addition to the base SSM permissions:
`ec2:DescribeInstances`, `ec2:{Authorize,Revoke,Describe}SecurityGroupIngress`, and
`ssm:GetParameter` (to read the cert pin).

## License

MIT License. See [LICENSE](./LICENSE).
