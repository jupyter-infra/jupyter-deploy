# Proxy

The **local proxy** is a small process on your machine that connects your browser to an
application deployed without a public URL. Instead of serving the application on a domain,
a template can expose it through the proxy, so the deployment needs no DNS record, no
certificate authority, and no OAuth app: your cloud credentials are the only prerequisite.

Templates opt into the proxy. Among the official templates, the
[**AWS EC2 JupyterLab Template**](../templates/aws-ec2-jupyterlab-template/index) uses it; the
others serve the application on your own domain.

## How it works

The proxy listens on a loopback address of your machine, such as `http://127.0.0.1:PORT`.
Your browser talks plain HTTP to it, and the proxy forwards each request to the remote host:

- over **TLS pinned** to the host's own self-signed certificate, so the connection is trusted
  without a certificate authority, and
- with a **short-lived token** proving your cloud identity, attached to every request
  (including WebSocket upgrades), which the remote host verifies before serving anything.

The proxy obtains the host address, the certificate pin, and the token by running
`jd proxy connect-info`, and runs it again before the token expires. Because the pin is on the
certificate rather than the address, the connection keeps working if the host's IP address
changes, for example after an instance stop and start.

Each template declares how to resolve these values; the proxy itself is cloud-agnostic. See
the [architecture of the AWS EC2 JupyterLab Template](../templates/aws-ec2-jupyterlab-template/architecture)
for a concrete example.

## Installation

The proxy ships as an optional extra of the CLI:

```bash
pip install "jupyter-deploy[proxy]"
```

The templates that use the proxy list this extra in their install command.

## Opening your application

`jd open` starts the proxy and opens a browser tab against it:

```bash
jd open
```

By default, the proxy runs in the foreground and stops when you stop the command
(for example with `Ctrl+C`).

To keep working in the same terminal, run the proxy in the background instead:

```bash
jd open --detached
```

## Managing a background proxy

The `jd proxy` commands manage a proxy that runs in the background:

```bash
# start a background proxy without opening a browser tab
jd proxy start

# open a browser tab against the running proxy
jd proxy open

# check whether the proxy is running, and see its details
jd proxy status
jd proxy show

# list its runs, newest first, and read the logs of one
jd proxy sessions
jd proxy logs
jd proxy logs --session-id SESSION_ID --lines 50

# stop it
jd proxy stop
```

At most one proxy runs per application. `jd open` replaces any proxy already running for the
application, whereas `jd proxy start` refuses to and leaves the running proxy in place.

## Automatic shutdown

A background proxy stops on its own so that it cannot outlive your session:

- after **two hours without activity** from your browser; an open WebSocket counts as activity
  even when no data flows, so a long-running kernel computation keeps its connection. Change the
  timeout with `--idle-timeout-seconds` on `jd proxy start`, or `--proxy-idle-timeout-seconds`
  on `jd open --detached`; pass `0` to disable it.
- when it can **no longer refresh its token**, for example after your cloud credentials expire.
  A temporary failure, such as a network interruption, does not stop it: the proxy keeps
  serving and retries.

A foreground proxy has no idle timeout: your terminal governs its lifetime.

## Troubleshooting the proxy

Each run of the proxy process is a *session* with its own logs, kept under `.jd-proxy/` in your
project directory. `jd proxy sessions` lists them with their state: `running`, `stopped` after a
clean shutdown, `failed`, or `dead` when the process went away without shutting down (for
example, it was killed).

If the proxy stops unexpectedly, run `jd proxy logs`: without `--session-id`, it reads the running
session, or the most recent one when none is running, which is usually the run that just stopped.

See the [`jd proxy`](../reference/project/proxy) and [`jd open`](../reference/project/open)
reference pages for every option.
