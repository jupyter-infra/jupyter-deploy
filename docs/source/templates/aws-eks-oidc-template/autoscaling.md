# AutoScaling

The template scales capacity along three independent axes:
- **workspaces** stop themselves when idle to release the pods they hold;
- Kubernetes scales component deployments up or down to adjust for traffic load; 
- the **cluster** adds and removes nodes dynamically to fit the running pods.

Together they keep enough capacity for active work without paying for idle nodes.

## Workspace idle shutdown

To avoid paying for workspaces nobody is using, the **Jupyter K8s** operator stops workspaces
after a period of no activity. Stopped workspaces free their pods (and thus let the
Cluster Autoscaler remove now-empty nodes) while retaining their persistent storage, so
a user can start again where they left off. Refer to
[Idle Shutdown documentation](https://jupyter-k8s.readthedocs.io/en/latest/dive-deeper/workspace-lifecycle/idle-shutdown.html)
for more details.

You can control the default idle shutdown configuration with these variables:

| Variable | Default | Purpose |
|---|---|---|
| `workspaces_idle_shutdown_enabled` | `true` | Turn idle shutdown on or off. |
| `workspaces_idle_shutdown_timeout_default` | `60` | Minutes of idleness before shutdown, unless a user overrides it. |
| `workspaces_idle_shutdown_timeout_min` | `15` | Lowest timeout a user may set (admin floor). |
| `workspaces_idle_shutdown_timeout_max` | `480` | Highest timeout a user may set (admin ceiling, caps cost exposure). |

```{note}
Users can set their own timeout per workspace, bounded by the min and max you set.
The floor is also bound by the operator's idle-check cadence (5 minutes by default).
```

Restart a stopped workspace at any time:
- from the [WebUI](web-ui)
- with `jd`: `jd server start --name my-workspace`
- with `kubectl`: `kubectl patch workspace <name> --type=merge -p '{"spec":{"desiredStatus":"Running"}}'`

## Node autoscaling

Each EKS managed node group has a size range — `min_size`, `desired_size`, and
`max_size` — set per node group in the `node_groups` variable. The default preset ships:

| Node group | Role | Instance type | min | desired | max |
|---|---|---|---|---|---|
| components | components | `t3.medium` | 1 | 2 | 3 |
| workspaces | workspaces | `c5.2xlarge` | 2 | 2 | 5 |

The [Cluster Autoscaler](https://github.com/kubernetes/autoscaler/tree/master/cluster-autoscaler)
runs on the cluster and adjusts each node group **within its min/max** in response to
demand:

- When pods can't be scheduled for lack of capacity (Pending pods), it adds nodes, up to `max_size`.
- When nodes sit underused, it removes them, down to `min_size`.


```{note}
The Cluster Autoscaler's image version tracks the cluster's Kubernetes minor version.
The template pins them together.
```
