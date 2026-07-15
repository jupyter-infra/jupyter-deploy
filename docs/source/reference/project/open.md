# `open`

Open the app in your web browser.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

Call <jd config> and <jd up> first.

For a multi-apps template, open a specific app with: <jd open --server-name SERVER_NAME>.
Pass --scope <scope>.

**Usage**:

```console
$ jd open [OPTIONS]
```

**Options**:

* `--server-name <str>`: Name of the server to open.
* `--scope <str>`: Scope or group the server belongs to.
* `-p, --path <path>`: Directory of the project to open.
* `--help`: Show this message and exit.
