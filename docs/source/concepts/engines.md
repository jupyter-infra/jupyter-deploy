# Engines

An **infrastructure-as-code engine** turns a template's declaration into real cloud
resources. It plans the changes needed to reach the desired state, applies them, and
tracks what it created so it can update or destroy those resources later.

`jupyter-deploy` treats the engine as a pluggable component. The core defines a
generic interface: configure, apply, destroy, and report progress. Each engine
provides a concrete implementation, but `jupyter-deploy` itself is engine-agnostic.

## Terraform

[Terraform](https://developer.hashicorp.com/terraform) is the engine used by the
official templates today.

- A template's `engine/` directory holds the Terraform files (`.tf`) and presets
  (`.tfvars`).
- `jd config` verifies Terraform is installed and prepares the working directory.
- `jd up` runs the equivalent of `terraform apply`; `jd down` runs the equivalent of
  `terraform destroy`.
- The engine writes **state** — a record of the resources it manages. `jupyter-deploy`
  keeps this state and backs it up to the [store](store) so it is not lost with your
  local machine.

You rarely interact with Terraform directly. When you need to — for debugging a
stuck deployment — the files live under `<PROJECT-DIR>/engine/`, and you can run
`terraform` commands there. See a template's `AGENT.md` for guidance.

## State and idempotency

Because the engine tracks state, running `jd up` again reconciles the deployment
toward the configured variables rather than recreating everything. Changing a
variable and re-running `jd config` followed by `jd up` applies just that change.

```{warning}
Running `jd up` against mismatched local state can fork a duplicate deployment. Do
not run overlapping `jd` or `terraform` operations against the same project from two
places at once.
```

## Engine logs

Each time the engine runs (`jd config`, `jd up`, or `jd down`), `jupyter-deploy`
captures its full output to an execution log under the project directory.

The `jd history` commands provide access to these engine logs:

```bash
# list the recent up logs
jd history list up

# show the latest up log (omit the command to show the most recent of any)
jd history show up

# show only the last 100 lines of the second-most-recent up log
jd history show up -n 2 -l 100

# prune old logs, keeping the most recent ones
jd history clear up
```

Logs are local to the project directory and git-ignored, so that unlike
the project files and engine state they are **not** pushed to the [store](store).
See the [`history`](../reference/project/history) command reference for full options.
