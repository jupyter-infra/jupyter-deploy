# Cloud Providers

A **cloud provider** is a vendor hosting a project's resources. A template selects a
provider, and `jupyter-deploy` talks to that provider's API to observe and operate
the deployment.

As with engines, `jupyter-deploy` provider-neutral: it defines a generic instruction
runner interface, and each provider implements it against its own SDK. `jupyter-deploy`
never depends on a provider SDK directly — provider support ships as an optional
install.

## Optional installs

`jupyter-deploy` supports optional installs targeting specific Cloud providers
or orchestration frameworks such as Kubernetes.

```bash
# AWS support
pip install "jupyter-deploy[aws]"

# AWS support with Kubernetes commands (for the EKS OIDC template)
pip install "jupyter-deploy[aws,k8s]"
```

A template's documentation lists the extras it needs. `jd config` checks for the
required tools (for example the AWS CLI, `kubectl`, or Helm) and prompts you to
install any that are missing.

## AWS

The official templates use AWS as cloud provider today. `jupyter-deploy` uses the
AWS SDK to back commands such as `jd health`, `jd server`, `jd cluster`, and
`jd image`.

Your local environment supplies the credentials. Configure them the way you would
for the AWS CLI; `jupyter-deploy` uses your default credential chain.

## Commands beyond the core workflow

Once a deployment is up, provider-backed commands let you observe and operate it.
Which of these apply depends on the template:

- **`jd show`:** displays details about the configuration of a specific deployment. 
- **`jd health`:** displays an health check for the components supporting the apps in the project.
- **`jd open`** — open the deployment entry point or a specific app.
- **`jd server`** — interact with the server(s) running your app.
- **`jd host` / `jd cluster`** — interact with the underlying host or cluster.
- **`jd component`** — interact with platform components (multi-user templates).
- **`jd image`** — manage application images.
- **`jd users` / `jd teams` / `jd organization`** — control access.

See the [CLI Reference](../reference/overview) for the full command surface.
