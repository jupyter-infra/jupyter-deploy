# `health`

Check the health of the full deployment stack.

**Usage**:

```console
$ jd health [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `-p, --path PATH`: Directory of the project.
* `--cluster`: Check only the cluster layer.
* `--load-balancer`: Check only the load balancer layer.
* `--components`: Check only the components layer.
* `--images`: Check only the images layer.
* `--connection`: Check only the end-to-end connection.
* `--json`: Output as JSON.
* `--help`: Show this message and exit.
