Components are the platform-level resources supporting your apps (e.g. router,
identity provider, controllers, node-level agents). Each one is backed by a Kubernetes
**Deployment** (a long-running workload), a **DaemonSet** (one pod per node, e.g. a CNI
or log shipper), a **StatefulSet**, a **CronJob** (a scheduled job), or a **HelmRelease**
(a chart managing a set of objects). You address a component by `--name`; `jd component
list` reports each one's name and type.

```bash
# list the components declared by this template (with their type)
jd component list

# check the status of a specific component
jd component status --name COMPONENT-NAME
```

`jd component status` and `jd component show` work for every component type. `show` reads
the full Kubernetes resource and prints it as JSON — the equivalent of `kubectl
describe`/`kubectl get -o json`. Use it to inspect the spec, replica counts, conditions,
and events.

```bash
jd component show --name COMPONENT-NAME
```

`jd component logs` fetches the logs of the component's pod (Deployment- and CronJob-backed
components only). Anything after `--` is passed straight to `kubectl logs`, so you can use
its flags — e.g. `--tail N` for the last N lines, `--since 10m`, `-f` to follow,
`--previous` for a crashed container's prior run, or `-c CONTAINER` to select a container.

```bash
# last 100 lines
jd component logs --name COMPONENT-NAME -- --tail 100

# follow the logs of the previous (crashed) container instance
jd component logs --name COMPONENT-NAME -- --previous -f
```

The remaining verbs depend on the component type (DaemonSet- and StatefulSet-backed
components support only `status` and `show`):

```bash
# restart a Deployment-backed component (rolling restart; not valid for a CronJob)
jd component restart --name COMPONENT-NAME

# trigger a one-off Job from a CronJob-backed component (not valid for a Deployment)
jd component trigger --name COMPONENT-NAME

# reconcile a HelmRelease-backed component (re-assert desired state; not valid for a Deployment or CronJob)
jd component reconcile --name COMPONENT-NAME
```

Helm only acts on the diff between chart releases, so an object deleted out-of-band (a
manual `kubectl delete`, an evicted CRD) is never recreated by a plain `helm upgrade`.
`jd component reconcile` re-applies the release's stored manifest to the live cluster,
recreating drifted or missing managed objects on demand. It requires a `helm` client on
the host.
