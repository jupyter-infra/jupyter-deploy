# `pool`

Interact with pools of hosts where apps and components run.

**Usage**:

```console
$ jd pool [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `list`: List the pools in the project.
* `show`: Display detailed information about a pool.
* `status`: Check the status of a pool.

## `pool list`

List the pools in the project.

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

## `pool show`

Display detailed information about a pool.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd pool show [OPTIONS]
```

**Options**:

* `--name <str>`: Name of the pool.  [required]
* `-p, --path <path>`: Directory of the project.
* `--json`: Output as JSON.
* `--help`: Show this message and exit.

## `pool status`

Check the status of a pool.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd pool status [OPTIONS]
```

**Options**:

* `--name <str>`: Name of the pool.  [required]
* `-p, --path <path>`: Directory of the project.
* `--help`: Show this message and exit.
