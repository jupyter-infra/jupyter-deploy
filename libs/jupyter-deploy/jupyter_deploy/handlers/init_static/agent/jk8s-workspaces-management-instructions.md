Each user app is a jupyter-k8s **Workspace** custom resource, exposed through the `server`
commands. Address a specific workspace with `--name`, and `--scope` to select the
Kubernetes namespace it lives in (defaults to the template's default namespace when
omitted). `jd server list` shows every workspace when `--name` is omitted; `status`,
`show`, `logs`, `exec`, and the lifecycle verbs require a `--name`. See the jupyter-k8s
[Workspace documentation](https://jupyter-k8s.readthedocs.io/en/latest/getting-started/run-workspaces.html)
for the custom resource itself.

```bash
# list all workspaces (optionally restricted to one namespace)
jd server list
jd server list --scope SCOPE
```

`jd server list` paginates: pass `--limit N` (`-n`) to cap the page size. When more
workspaces remain, the command prints a continuation token — pass it back with
`--continue-from TOKEN` to fetch the next page. Without a token, a large cluster returns a
truncated list, so loop until no token is returned.

```bash
# first page of 20, then the next page using the returned token
jd server list --limit 20
jd server list --limit 20 --continue-from TOKEN
```

`jd server status` prints one of `Running`, `Starting`, `Stopping`, `Stopped` or
`Degraded`, derived from the Workspace's conditions. While a workspace starts, or
after a start has failed, the template may add the current step or the failure
reason in parentheses after the word. For the full detail, including each
condition's `message`, use `jd server show --json`, which prints the whole Workspace.

```bash
jd server status --name WORKSPACE-NAME --scope SCOPE
```

`jd server show` returns the full Workspace custom resource as JSON (spec, conditions,
the backing Deployment name, the access URL) — useful for diagnosing why a workspace is
not `Running`.

```bash
jd server show --name WORKSPACE-NAME --scope SCOPE
```

Stop and start patch the Workspace's `desiredStatus`; the operator reconciles it. Stopping
keeps the persistent volume, so data survives a stop/start cycle.

```bash
jd server stop --name WORKSPACE-NAME --scope SCOPE
jd server start --name WORKSPACE-NAME --scope SCOPE
```

Logs, exec, and connect act on the running workspace pod. Arguments after `--` on
`jd server logs` pass straight to `kubectl logs` (e.g. `--tail 100`, `--since 10m`, `-f`).

```bash
# tail the last 100 log lines of the workspace
jd server logs --name WORKSPACE-NAME --scope SCOPE -- --tail 100

# run a one-off command inside the workspace pod with kubectl exec
jd server exec --name WORKSPACE-NAME --scope SCOPE -- ls -la /home/jovyan

# open an interactive shell in the workspace pod with kubectl exec
jd server connect --name WORKSPACE-NAME --scope SCOPE
```
