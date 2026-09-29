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

A token command signals a **transient** failure (network blip, throttling) by exiting
`75` (`EX_TEMPFAIL`): the proxy keeps serving on its last-good credential and retries.
Any other non-zero exit is permanent — the proxy can no longer serve anything, so it
stops itself and exits `78`.

## Auto-shutdown

The proxy ends its own process in two cases, so a background one cannot outlive its
session:

- **the credential can no longer be refreshed** (the token command failed permanently)
  — exits `78`, leaving `status.json` behind as the record that it failed rather than
  stopped; the reason is in the `NNNN.log` files beside it;
- **no client activity for `--idle-timeout-seconds`** (default 7200, two hours) — exits
  `0` and removes `status.json`, like any clean stop. Pass `0` to disable, which is
  what `jd open` does when it runs the proxy in the foreground: there the terminal
  governs the lifetime.

Activity means traffic from a client. **An open WebSocket counts even while no frames
flow**, so a kernel computing silently for hours keeps its tunnel, and **a response still
streaming counts on every chunk**, so a long transfer is never cut off mid-flight.
Credential refreshes do not count — they are the proxy's own traffic.

Part of the [jupyter-deploy](https://github.com/jupyter-infra/jupyter-deploy) project.

## License

The `jupyter-deploy-client-proxy` package is licensed under the [MIT License](https://github.com/jupyter-infra/jupyter-deploy/blob/main/libs/jupyter-deploy-client-proxy/LICENSE).
