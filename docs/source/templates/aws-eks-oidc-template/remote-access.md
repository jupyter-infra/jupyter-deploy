# Remote Access

With the `enable_default_vscode_app` template variable set to `true`, users open workspaces in
**VS Code**, **Cursor** or **Kiro** running on their own machine, over SSH. The template then
builds a second workspace image, the VS Code image, and offers a VS Code card in the namespaces
whose `workspace_namespaces` entry lists `vscode` in `templates`, or in the single `default`
namespace when no namespaces are declared, plus a VS Code GPU card when `enable_default_gpu_pool`
is on.

A workspace created from a VS Code card runs an SSH server on its pod's loopback interface and
a `ws-proxy` sidecar that relays the SSH stream between the HTTPS entry point and that server.
The VS Code image ships the same **Claude Code** and **Codex** agents as the JupyterLab image,
so a terminal in the editor has them with no setup, with Bedrock access as described in
[Bedrock Integration](bedrock-integration.md).

Set the flag in the `overrides:` block of `variables.yaml`, then run `jd config` and `jd up`:

```yaml
overrides:
  enable_default_vscode_app: true
```

The first apply builds the VS Code image and copies the `ws-proxy` sidecar image from the digest
the template pins into the deployment's ECR, a few minutes in AWS CodeBuild. It also restarts the
operator and Authmiddleware once; running workspaces keep running.
Bump `workspace_app_vscode_image_build` to rebuild the image, as
`workspace_app_jupyterlab_image_build` does for JupyterLab; `workspace_app_ws_proxy_image_build`
does the same for the sidecar copy, which is also copied again when a template release changes
the pinned digest.

## How a connection is authorized

1. On the user's machine, the [kubectl-workspace](https://github.com/jupyter-infra/kubectl-workspace)
   plugin asks the **Jupyter K8s** operator for a connection with the user's kubeconfig
   credential, the same GitHub identity `kubectl` uses. The `github-rbac` chart grants the
   namespace's teams the `workspaceconnections` permission this takes.
2. The operator checks that the user may reach the workspace, signs a token that lives five
   minutes, and answers with a `wss://` URL for the workspace.
3. The plugin opens a WebSocket to that URL through the Network Load Balancer and Traefik, with
   the token in the `Authorization` header. Authmiddleware verifies the token, Traefik
   forwards the stream to the workspace's `ws-proxy` sidecar, and the sidecar bridges it to the
   SSH server on `127.0.0.1:2222`.

No SSH key is created or distributed. The SSH server binds the pod's loopback interface, so
nothing outside the pod reaches it, and the workspace-ingress NetworkPolicy admits the sidecar
port from the Traefik pods only. The operator namespace keeps its access to the application
port, which it probes for the idle detection of JupyterLab workspaces. The host key persists in
the workspace's home volume, so a restart keeps its fingerprint.

## Connect from your machine

Install the [kubectl-workspace](https://github.com/jupyter-infra/kubectl-workspace) plugin and
configure `kubectl` for the cluster, the way the kubectl access page of the [Web UI](web-ui.md)
sets it up. Then install the SSH configuration entry once per cluster and open workspaces from it:

```bash
# once per cluster
kubectl workspace ssh-config --write --context <context>

# open a workspace in a desktop editor
kubectl workspace open <workspace> --editor <vscode|cursor|kiro>

# or reach it from any SSH client
ssh <workspace>.<namespace>.<cluster>.jk8s
```

Each editor needs its Remote-SSH extension and installs its own remote server in the workspace
on first connect. Refer to the plugin's README for the editor setup and the command flags.

## Logs and shell access

A VS Code workspace pod holds two containers, `workspace` and the `ws-proxy` sidecar. `jd server
logs`, `jd server exec` and `jd server connect` act on `workspace` and print the container they
picked; pass `--service ws-proxy` for the sidecar's logs.

`jd image list` shows the VS Code image and the `ws-proxy` sidecar copy beside the JupyterLab
one, marked as not built while the flag is off, and `jd health` skips them, naming the flag they
need. `jd image status --name vscode` and
`jd image vulnerabilities --name vscode` report on the VS Code image, `--name ws-proxy` on the
sidecar copy; with the flag off they say the image is not built. With more than one image built,
the per-image `jd image` commands need `--name`.

## Limits

- **No idle shutdown**: nothing in a VS Code workspace reports editor activity to the operator
  yet, so VS Code cards carry no idle policy and `workspace_templates` configs with
  `app: vscode` refuse `idle_minutes`. Stop a VS Code workspace from the Web UI or with
  `jd server stop`.
- **No browser app**: the Web UI lists VS Code workspaces and starts and stops them; its Open
  button targets the browser URL, which nothing answers in a VS Code workspace.

## Custom VS Code cards

A `workspace_templates` config with `app: vscode` renders a VS Code card on the pool that offers
it, with the same keys as a JupyterLab config except `idle_minutes`:

```yaml
overrides:
  enable_default_vscode_app: true
  workspace_templates:
    - name: vscode-gpu-p
      app: vscode
      gpus: "1"
      cpu: "22"
      memory: "200Gi"
  workspace_nodepools:
    # ... the CPU pool ...
    - name: workspace-gpu-p
      instance_families: p4d,p5,p5en
      disk_size_gb: "200"
      max_cpu: "384"
      max_memory: "3000Gi"
      accelerator: nvidia
      templates: vscode-gpu-p
```

## Turning it off

Setting `enable_default_vscode_app` back to `false` removes the VS Code cards and the WebSocket
access strategy. Delete the VS Code workspaces first: `jd config` refuses to remove a template a
live workspace still uses.
