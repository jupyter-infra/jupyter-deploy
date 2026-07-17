# Store

A **store** is a durable, remote copy of your project. A project directory lives on
your local machine, but the infrastructure it manages lives in the cloud. The store
bridges the two, so a deployment survives an accidental directory deletion, or the
loss of the compute environment that deployed the project.

## What the store holds

For each project, the store keeps:

- the **project files** — `manifest.yaml`, `variables.yaml`, and the `engine/` and
  `services/` directories, and
- the **infrastructure-as-code state** — the engine's record of the resources it
  manages.

Each project within a store is identified by a unique **project ID**.

## When backups happen

`jd up` automatically backs the project up to the store after a run, even if the
run ends in failure. This means the remote copy stays current with each deploy, and
a failed first deploy still persists its state so a retry does not lose track of
partially-created resources.

## Restoring a project

Because the store holds both the project files and the infrastructure state, you can
rebuild a project's local directory anywhere — on a new machine, or after losing the
original directory — without touching the running cloud resources.

Restore with `jd init`, passing the project ID and the store to restore from:

```bash
jd init <PROJECT-DIR> \
  --restore-project <PROJECT-ID> \
  --store-type s3-only
```

This recreates `<PROJECT-DIR>` from the stored copy. You can then run `jd config`
and `jd up` again.

```{note}
If your project includes sensitive variables, run: jd config --restore-secrets
```

```{note}
Restoring re-hydrates the local project only; it does not change any cloud resources.
The restored state must still match what is actually deployed. Avoid restoring onto a
project that another machine is concurrently operating.
```

## Store types

`jupyter-deploy` supports more than one store backend, identified by `--store-type`:

- **`s3-only`** — project files and state in an S3 bucket.
- **`s3-ddb`** — S3 for data, with a DynamoDB table for indexing and locking.

## Managing stored projects

The `jd projects` commands operate on the store rather than a local directory:

```bash
# list projects in a store
jd projects list --store-type s3-only

# show details of a stored project
jd projects show <PROJECT-ID> --store-type s3-only

# delete a stored project's data
jd projects delete <PROJECT-ID> --store-type s3-only
```

```{note}
Deleting a stored project removes only the remote copy, it does **not** destroy the
cloud resources. Tear a deployment down with `jd down` first, then remove its store
entry.
```

See the [Store Commands](../reference/store-commands) reference for full details.
