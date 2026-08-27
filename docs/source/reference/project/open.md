# `open`

Open the app in your web browser.

Run either from a project directory that you created with <jd init>;
or pass --path <project-dir>.

Call <jd config> and <jd up> first.

For a multi-apps template, open a specific app with: <jd open --server-name SERVER_NAME>.
Pass --scope <scope>.

For templates that route traffic through the local proxy, <jd open> starts a local process
in the foreground; pass --detached or -d to run the proxy process in the background, and
use <jd proxy> commands to manage it afterwards.

**Usage**:

```console
$ jd open [OPTIONS]
```

**Options**:

* `--server-name <str>`: Name of the server to open.
* `--scope <str>`: Scope or group the server belongs to.
* `-p, --path <path>`: Directory of the project to open.
* `-d, --detached`: Run the local proxy in the background.
* `--help`: Show this message and exit.
