# Concepts

`jupyter-deploy` deploys interactive applications without asking you to learn a
cloud provider or an infrastructure-as-code engine. You pick a **template**, set a
few variables, and run three commands: `jd init`, `jd config`, `jd up`.

`jupyter-deploy` separates *what* you deploy from *how* it gets deployed.

## The CLI
`jupyter-deploy` (or `jd`) is the command-line tool you interact with.
It orchestrates the pieces below: scaffolding projects, driving the engine, talking to
the provider, and backing projects up to a store. It ships as a Python package,
cloud-provider and engine agnostic.

## Templates
A [**template**](templates) is a reusable blueprint.

Templates ship as Python packages distinct from the CLI. They bundle the configuration files
(e.g. HCL, Dockerfile), describes variables, and provides defaults. 

A templates declares what to deploy:
  - cloud resources on a [**cloud provider**](providers)
  - to run one or several [**application images**](application-images)
and how:
  - the [**infrastructure-as-code engine**](engines).

`jupyter-deploy` itself stays neutral: it defines the interfaces, and each template
selects a concrete engine and provider. That is why the same `jd` commands work
across templates that deploy very different infrastructure.

## Projects
A [**project**](projects) is your instance of a template. It lives in a local directory
that you create by running `jd init`. You can view templates as a class in 
Object-oriented programming, and a project as an instance of such a class.

A project is fully yours, you may modify it as you please, without impacting the template
that you used to create it.

## Stores
[**stores**](store) keep a durable copy of each project: its files and its
infrastructure state. There are several types of stores, templates declares which one to use
by default. For example, the official AWS templates use an S3 bucket in your AWS account.
A deployment saved in a store survives even if you accidentally delete the local directory.

## The workflow

Every deployment follows the same three steps, regardless of template:

1. **`jd init <PROJECT-DIR>`** — choose a template and scaffold a project into a
   local directory.
2. **`jd config`** — set variable values (interactively or in `variables.yaml`) and
   verify the required tools are installed.
3. **`jd up`** — create or update the cloud resources, then back the project up to
   the store.

From there, `jd` commands let you observe and operate the deployment (`jd health`,
`jd open`, `jd show`), manage the application (`jd server`, `jd component`), control
access (`jd users`, `jd teams`), and eventually tear it down (`jd down`).

## What's next

```{toctree}
:maxdepth: 1

templates
projects
engines
providers
application-images
store
```

