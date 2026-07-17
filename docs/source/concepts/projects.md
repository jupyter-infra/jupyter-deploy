# Projects

A **project** is your instance of a [template](templates): a local directory holding
one deployment's configuration and state. Where a template is a shared, versioned
blueprint, a project is specific to you: it carries your variable values, your image
customizations, and the record of the cloud resources you have deployed. Creating a
project is the moment a template becomes something you can deploy and operate.

## Creating a project

`jd init <PROJECT-DIR>` creates a project by scaffolding a chosen template into a local
directory:

```bash
mkdir my-deployment && cd my-deployment
jd init .
```

The scaffolded directory is a self-contained copy of the template — yours to edit and
optionally to commit to version control:

```
<PROJECT-DIR>/
├── manifest.yaml       # Template metadata and provider commands
├── variables.yaml      # Variable definitions and configuration presets
├── AGENT.md            # Template-specific instructions for AI assistants
├── .gitignore
├── engine/             # Infrastructure-as-code files (e.g., Terraform .tf files)
└── services/           # Application service definitions and configurations
```

Because the project holds its own copy of the template files, it does not track the
installed template package after creation. Upgrading the template package does not
change an existing project; likewise, a new variable added to a template only applies
once you add it to that project's `variables.yaml`. A fresh `jd init` always picks up
the version of the template installed in your Python environment.

## How jupyter-deploy finds your project

Most `jd` commands operate on one project. They locate it in one of two ways:

- **Current working directory** — run the command from inside the project directory and
  `jupyter-deploy` uses it automatically. This is the common case.
- **`-p` / `--path`** — point at the project explicitly from anywhere:

  ```bash
  jd up --path path/to/my-deployment
  ```

Exceptions:
- `jd init` creates a project rather than operating on one, so it takes the target directory
as its argument.
- `jd config` does not support the `-p`/`--path` flag, always run it from the project directory.


## Configuring and deploying

Configuring a project means setting the values of its [template](templates) variables.
`jupyter-deploy` offers three ways to do this, which you can mix freely.

**Interactively.** Running `jd config` with no arguments walks you through the
variables, prompting for each with its description and default:

```bash
jd config
```

This is the easiest way to start — it surfaces required variables and validates each
value as you enter it.

**By editing `variables.yaml`.** The project's `variables.yaml` holds every variable,
grouped into `required:` (values you must supply), `required_sensitive:` (secrets, see
below), and `overrides:` (variables with template defaults you can change). If you
prefer a file-based experience, edit it directly to set values:

```yaml
required:
  domain: example.com
  subdomain: jupyter

overrides:
  volume_size_gb: 50
  log_files_retention_days: 90
```

**With flags.** Pass values on the command line, using the variable name in kebab-case
as a flag:

```bash
jd config --volume-size-gb 50 --log-files-retention-days 90
```

To see every variable a template exposes — with its flag name, type, and description —
run:

```bash
jd config --help
```

Once configured, create the cloud resources with `jd up`.

Each `jd config`, `jd up`, and `jd down` run captures the engine's full output to an
execution log in the project, which you can inspect with `jd history` — see
[Engine logs](engines.md#engine-logs).

## Projects store

A project lives on your local machine, but the deployment it manages lives in the
cloud. Project [stores](store) bridge the two: `jd up` backs the project — its files and its
infrastructure state — up to a remote store, keyed by a unique **project ID**. That
backup lets you restore the project on another machine, or after losing the local
directory, without disturbing the running resources. See [The Store](store) for
backup, restore, and the `jd projects` commands.

## Sensitive variables

Some variables hold secrets, such as OAuth client secrets or API tokens, and a template
marks these as **sensitive**. `jupyter-deploy` treats them differently from ordinary
variables so they don't sit in plaintext in your project:

- When you set a sensitive value (interactively, by flag, or in `variables.yaml`),
  `jupyter-deploy` records it for the deployment but then **masks it in
  `variables.yaml`**. The real value is handed to the engine and, for the official templates,
  stored in a managed secret (for example AWS Secrets Manager) rather than kept locally.
- Because the value is masked locally, a project restored from the [store](store) comes
  back with its secrets masked. `jupyter-deploy` allows you to restore these values locally
  with `jd config --restore-secrets`. Afterwards, you can run `jd up` to bring your actual
  cloud resources in line with the project configuration.

## Tearing down a project

Removing a deployment is a two-step operation, because the cloud resources and the
store copy are independent — deleting one does not affect the other.

First, destroy the cloud resources with `jd down`, run from the project directory (or
with `--path`):

```bash
jd down
```

This is the inverse of `jd up`: the engine destroys everything it provisioned. Let it
run to completion, interrupting a destroy can leave orphaned resources behind. As with
`jd up`, the run is captured to an execution log you can review with
`jd history show down`.

Once the resources are gone, you can optionally clean up the project's copy in the
store. The stored copy is small and inexpensive to keep, and deleting it never touches
cloud resources. Refer to [The Store](store) for more details.
