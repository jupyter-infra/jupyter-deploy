# jupyter-deploy-client-proxy

A local client that routes an app from your `http://localhost` to a
jupyter-deploy-managed remote host. It runs a configured **token command**
(the exec-credential contract, à la `kubectl` `ExecCredential` / `aws eks get-token`),
receives a JSON connection bundle on stdout, and proxies plain `http://localhost`
to the remote host over pinned self-signed TLS — injecting the bundle's rotating
headers on every request and the WebSocket upgrade.

It stays cloud-agnostic — it imports nothing cloud-specific and works against any
self-signed-TLS + bearer endpoint:

```
jupyter-deploy-client-proxy --token-command "jd proxy connect-info" --listen-port 8080
```

## Connection bundle

The token command emits, on stdout:

```json
{
  "host": "203.0.113.7", "port": 443,
  "ca_cert": "-----BEGIN CERTIFICATE-----\n...",
  "headers": { "Authorization": "Bearer ...", "x-k8s-aws-id": "..." },
  "expires_at": "2026-06-10T18:01:00Z"
}
```

The proxy re-execs the command on a margin before `expires_at`, reconnecting with
the fresh endpoint/pin/credential and keeping `localhost:PORT` stable.

Part of the [jupyter-deploy](https://github.com/jupyter-infra/jupyter-deploy) project.
