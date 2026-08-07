# AutoScaling

The template scales capacity along three independent axes:
- **workspaces** stop themselves when idle to release the pods they hold;
- Kubernetes scales component deployments up or down to adjust for traffic load; 
- the **cluster** adds and removes nodes dynamically to fit the running pods.

Together they keep enough capacity for active work without paying for idle nodes.

## Workspace idle shutdown

To avoid paying for workspaces nobody is using, the **Jupyter K8s** operator stops workspaces
after a period of no activity. Stopped workspaces free their pods (and thus let Karpenter
reclaim now-empty nodes) while retaining their persistent storage, so
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

## Component autoscaling

The routing tier (Traefik, Authmiddleware, and the Web UI) scales its pod count with
[KEDA](https://keda.sh/), driven by the number of open connections Traefik reports to
Prometheus. As traffic rises, KEDA adds replicas; as it falls, it removes them (the Web
UI and Authmiddleware never scale below one replica). You do not configure this directly —
the thresholds ship with the template.

## Node autoscaling

The cluster runs three kinds of node pool, each tuned for a different job:

| Pool | Role | Provisioner | Scaling |
|---|---|---|---|
| `platform` | Platform services (JupyterK8s operator, Karpenter, Keda, etc.) | EKS managed node group | Cluster Autoscaler, `platform_min_size`–`platform_max_size` |
| `routing` | Routing tier (Traefik, Dex, OAuth2 Proxy, Authmiddleware, Web UI) | Karpenter NodePool | Always-on; grows with the KEDA-scaled routing pods |
| `workspace-cpu` (or any pools you configure) | User workspace pods | Karpenter NodePool | Scale-to-zero |

The `platform` pool holds a small, stable set of control-plane services and stays within
its fixed size range, managed by the
[Cluster Autoscaler](https://github.com/kubernetes/autoscaler/tree/master/cluster-autoscaler).

[Karpenter](https://karpenter.sh/) provisions nodes for the `routing` and workspace pools
just-in-time: when a pod can't be scheduled, Karpenter launches a right-sized EC2 instance
for it, and consolidates or removes nodes once they're empty. This lets workspace pools
**scale to zero**: when the last workspace on a node stops (see idle shutdown above),
Karpenter reclaims the node, so idle capacity costs nothing.

You control node pools through admin variables:

| Variable | Default | Purpose |
|---|---|---|
| `platform_instance_types` | `["m5.large"]` | Instance types for the platform managed node group. |
| `platform_min_size` / `platform_max_size` | `2` / `3` | Size range for the platform node group. |
| `routing_instance_categories` | `["c", "m"]` | Instance categories Karpenter may pick for routing nodes. |
| `routing_max_cpu` / `routing_max_memory` | `32` / `128Gi` | Ceiling on total routing-pool capacity. |
| `workspace_nodepools` | one `workspace-cpu` pool | List of workspace pools, each with its own instance families and CPU/memory ceilings. |
| `enable_gpu_pool` | `false` | Adds the built-in GPU pool, the NVIDIA device plugin, and the `jupyterlab-gpu` template. |
| `node_expire_after` | `504h` | Maximum node lifetime before Karpenter recycles it. |

Add a CPU workspace pool by appending an entry to `workspace_nodepools`: no new
variables required. For GPU capacity, set `enable_gpu_pool: true` instead: the
template adds a built-in `workspace-gpu` pool (`g4dn,g5` on-demand instances,
fleet ceiling `max_gpus: "4"`), installs the NVIDIA device plugin, and ships the
`jupyterlab-gpu` workspace template, a fixed shape (one GPU with pinned
cpu/memory) fenced to the pool by its role taint. To customize the GPU pool,
define your own `workspace-gpu` entry in `workspace_nodepools`, which takes
precedence over the built-in; the optional per-entry keys are `role` (the
label/taint value), `max_gpus` (fleet GPU ceiling), and `gpu` (`"true"` adds the
`nvidia.com/gpu.present` label the device plugin selects on). Delete GPU
workspaces before turning the flag off: disabling removes the pool and the
template they depend on. First GPU use on an account without prior GPU usage
requires raising the `Running On-Demand G and VT instances` service quota (see
the troubleshooting guide). Inspect pools at runtime with
`jd pool list`, `jd pool show --name <pool>`, and `jd pool status --name <pool>`.

```{note}
The Cluster Autoscaler's image version tracks the cluster's Kubernetes minor version.
The template pins them together.
```
