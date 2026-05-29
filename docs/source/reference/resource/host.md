# `host`

Interact with the host machine(s) running your app(s).

**Usage**:

```console
$ jd host [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `status`: Check the status of the host machine.
* `stop`: Stop the host machine.
* `start`: Start the host machine.
* `restart`: Restart the host machine.
* `connect`: Start an SSH-style connection to the host...
* `exec`: Execute a non-interactive command on the...
* `list`: List the hosts in the project.
* `show`: Display detailed information about a host.

## `host status`

Check the status of the host machine.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd host status [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the host to check status for.
* `-p, --path PATH`: Directory of the project whose host to check status.
* `--for [connection]`: Check the status of specific agent or access point within the host.
* `--help`: Show this message and exit.

## `host stop`

Stop the host machine.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd host stop [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the host to stop.
* `-p, --path PATH`: Directory of the project whose host to stop.
* `--help`: Show this message and exit.

## `host start`

Start the host machine.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd host start [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the host to start.
* `-p, --path PATH`: Directory of the project whose host to start.
* `--help`: Show this message and exit.

## `host restart`

Restart the host machine.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd host restart [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the host to restart.
* `-p, --path PATH`: Directory of the project.
* `--help`: Show this message and exit.

## `host connect`

Start an SSH-style connection to the host machine.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd host connect [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the host to connect to.
* `-p, --path PATH`: Directory of the project.
* `--help`: Show this message and exit.

## `host exec`

Execute a non-interactive command on the host machine.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

Pass the command after '--', for example:

<jd host exec -- df -h>

<jd host exec -- "docker container list | grep jupyter">

**Usage**:

```console
$ jd host exec [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the host on which to execute the command.
* `-p, --path PATH`: Directory of the project.
* `--help`: Show this message and exit.

## `host list`

List the hosts in the project.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd host list [OPTIONS]
```

**Options**:

* `-p, --path PATH`: Directory of the project whose hosts to list.
* `--query TEXT`: Filter expression to narrow the list of hosts.
* `-n, --limit INTEGER`: Maximum number of hosts to return.
* `--continue-from TEXT`: Continuation token from a previous list call.
* `--json`: Output as JSON.
* `--help`: Show this message and exit.

## `host show`

Display detailed information about a host.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd host show [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the host to show details for.  [required]
* `-p, --path PATH`: Directory of the project.
* `--json`: Output as JSON.
* `--help`: Show this message and exit.
