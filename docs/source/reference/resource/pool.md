# `pool`

Interact with the node pools managing workspace and routing nodes.

**Usage**:

```console
$ jd pool [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `list`: List node pools with node count,...
* `status`: Show detailed status for a node pool.
* `scaling`: Show recent node provisioning and...

## `pool list`

List node pools with node count, CPU/memory limits, and Ready status.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd pool list [OPTIONS]
```

**Options**:

* `-p, --path <path>`: Directory of the project.
* `--json`: Output as JSON.
* `--help`: Show this message and exit.

## `pool status`

Show detailed status for a node pool.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd pool status [OPTIONS]
```

**Options**:

* `--name <str>`: Name of the node pool.  [required]
* `-p, --path <path>`: Directory of the project.
* `--json`: Output as JSON.
* `--help`: Show this message and exit.

## `pool scaling`

Show recent node provisioning and consolidation events.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd pool scaling [OPTIONS]
```

**Options**:

* `-p, --path <path>`: Directory of the project.
* `--json`: Output as JSON.
* `--help`: Show this message and exit.
