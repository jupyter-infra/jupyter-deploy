# `server`

Interact with the server(s) running your app(s).

**Usage**:

```console
$ jd server [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `status`: Sends a health check to the services.
* `start`: Start the services.
* `stop`: Stop the services.
* `restart`: Restart the services.
* `logs`: Print the logs of the service to terminal.
* `exec`: Execute a non-interactive command inside a...
* `connect`: Start an interactive shell session inside...
* `list`: List servers in the project.
* `show`: Display detailed information about a server.

## `server status`

Sends a health check to the services.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd server status [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the server to check status for.
* `-p, --path PATH`: Directory of the project whose server to send a health check.
* `--scope TEXT`: Scope or group the server belongs to.
* `--help`: Show this message and exit.

## `server start`

Start the services.

By default, starts all services. Specify --service to target a specific service.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd server start [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the server to start.
* `-p, --path PATH`: Directory of the project whose server to start.
* `-s, --service TEXT`: Service to start ('all', 'jupyter', or other available services).  [default: all]
* `--scope TEXT`: Scope or group the server belongs to.
* `--help`: Show this message and exit.

## `server stop`

Stop the services.

By default, stops all services. Specify --service to target a specific service.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd server stop [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the server to stop.
* `-p, --path PATH`: Directory of the project whose server to stop.
* `-s, --service TEXT`: Service to stop ('all', 'jupyter', or other available services).  [default: all]
* `--scope TEXT`: Scope or group the server belongs to.
* `--help`: Show this message and exit.

## `server restart`

Restart the services.

By default, restarts all services. Specify --service to target a specific service.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd server restart [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the server to restart.
* `-p, --path PATH`: Directory of the project whose server to restart.
* `-s, --service TEXT`: Service to restart ('all', 'jupyter', or other available services).  [default: all]
* `--scope TEXT`: Scope or group the server belongs to.
* `--help`: Show this message and exit.

## `server logs`

Print the logs of the service to terminal.

By default, logs your main application service. Specify --service to target a specific service.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

You can pass additional arguments after '--'

For example, if the underlying engine is docker, use <jd server logs -- -n 100> to retrieve 100 log lines.

To apply host-side filters, use <jd server logs -- "| grep SEARCH_VALUE">

Note: invalid characters may prevent logs to be displayed. To view the full logs, connect to your host
with <jd host connect>.

**Usage**:

```console
$ jd server logs [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the server whose logs to display.
* `-p, --path PATH`: Directory of the project whose server logs to display.
* `-s, --service TEXT`: Name of the service whose logs to display.  [default: default]
* `--scope TEXT`: Scope or group the server belongs to.
* `--help`: Show this message and exit.

## `server exec`

Execute a non-interactive command inside a service container.

By default, executes in your main application service. Specify --service to target a specific service.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

Pass the command after '--', for example:

<jd server exec -- pwd>

<jd server exec -s SERVICE -- "df -h">

Note: the commands you can execute depend on the service;
distroless images in particular expose very limited commands.

**Usage**:

```console
$ jd server exec [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the server in which to execute the command.
* `-p, --path PATH`: Directory of the project.
* `-s, --service TEXT`: Name of the service in which to execute the command.  [default: default]
* `--scope TEXT`: Scope or group the server belongs to.
* `--help`: Show this message and exit.

## `server connect`

Start an interactive shell session inside a service container.

By default, connects to your main application service. Specify --service to target a specific service.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

Example:

<jd server connect>

<jd server connect -s SERVICE>

Note: you may not be able to connect to all services;
some containers do not have any shell installed.

**Usage**:

```console
$ jd server connect [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the server to connect to.
* `-p, --path PATH`: Directory of the project.
* `-s, --service TEXT`: Name of the service to connect to.  [default: default]
* `--scope TEXT`: Scope or group the server belongs to.
* `--help`: Show this message and exit.

## `server list`

List servers in the project.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd server list [OPTIONS]
```

**Options**:

* `-p, --path PATH`: Directory of the project whose servers to list.
* `--scope TEXT`: Scope or group to list servers from.
* `-n, --limit INTEGER`: Maximum number of servers to return.
* `--continue-from TEXT`: Continuation token from a previous list call.
* `--json`: Output as JSON.
* `--help`: Show this message and exit.

## `server show`

Display detailed information about a server.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

**Usage**:

```console
$ jd server show [OPTIONS]
```

**Options**:

* `--name TEXT`: Name of the server to show details for.  [required]
* `-p, --path PATH`: Directory of the project.
* `--scope TEXT`: Scope or group the server belongs to.
* `--json`: Output as JSON.
* `--help`: Show this message and exit.
