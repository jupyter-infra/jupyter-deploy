# `cluster`

Interact with the cluster managing the host machines where your apps run.

**Usage**:

```console
$ jd cluster [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `login`: Configure your local client to access the...
* `status`: Check the status of the cluster control...
* `show`: Display detailed information about the...

## `cluster login`

Configure your local client to access the cluster.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd cluster login [OPTIONS]
```

**Options**:

* `-p, --path PATH`: Directory of the project whose cluster to configure access for.
* `--help`: Show this message and exit.

## `cluster status`

Check the status of the cluster control plane.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd cluster status [OPTIONS]
```

**Options**:

* `-p, --path PATH`: Directory of the project whose cluster to check status.
* `--help`: Show this message and exit.

## `cluster show`

Display detailed information about the cluster.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd cluster show [OPTIONS]
```

**Options**:

* `-p, --path PATH`: Directory of the project whose cluster to show details for.
* `--json`: Output as JSON.
* `--help`: Show this message and exit.
