# Application Images

Each application you deploy runs from a **container image**. Notable application
software include **JupyterLab**, **Jupyter Notebooks** or IDEs such as **VS Code**.

This page explains what an image is, how templates build and expose
them, and how to keep them free of known vulnerabilities.

## Containers and images

A **container** is an isolated process that runs your application with its own filesystem,
libraries, and dependencies, independent of whatever else is on the host. This is what
makes a deployment reproducible: the container carries everything the application needs,
so it behaves the same wherever it runs.

A container starts from an **image** — a read-only, layered package containing the
operating-system files, language runtime, libraries, and your application code. The most
common way to build and run images is [Docker](https://docs.docker.com/get-started/),
whose format is a de-facto standard; the images `jupyter-deploy` uses follow it. In short:
an image is the blueprint, a container is a running instance of it.

## Default and custom images

Each template ships **default image(s)** for its application(s). For example,
the **AWS Base Template** and the **AWS EKS OIDC Template** both provide a JupyterLab image
that you can use as-is to get started.

Images are yours to **extend**: you can customize their `Dockerfile` in your project.
For example, you may add system packages, Python libraries or startup scripts.
Because the `Dockerfile` lives in your project directory, your customizations
are versioned alongside the rest of the deployment.


## How jupyter-deploy manages images

Once deployed, you can discover and manage a project's application images with the
`jd image` commands:

```bash
# list the application images for this project
jd image list

# show where an image lives and its tags
jd image show --name jupyterlab

# list available tags
jd image tags --name jupyterlab
```

See the [`image`](../reference/resource/image) command reference for the full command set.

## Vulnerabilities and why patching matters

Software ships with defects, and some of those defects are security vulnerabilities.
Publicly known ones are catalogued as **CVEs** (Common Vulnerabilities and Exposures), each
with a unique identifier like `CVE-2024-12345`. A container image can accumulate CVEs in any
of its layers: the base operating-system packages, the language runtime, or the
application's own dependencies.

Security researchers (and hackers) find software vulnerabilities constantly.
**Rebuilding and redeploying regularly** pulls in upstream security fixes and is the most reliable
way to keep exposure low. For a `jupyter-deploy` project, that means periodically re-running the
build (for example by bumping the image build tag) and `jd up`.

### Severity versus exploitability

Not every CVE is equally urgent, and two different measures matter:

- **Severity** — how bad the impact would be *if* the vulnerability were exploited. This is
  what the familiar CRITICAL / HIGH / MEDIUM / LOW ratings (from
  [CVSS](https://www.first.org/cvss/)) describe.
- **Exploitability** — how *likely* the vulnerability is to actually be exploited. A
  high-severity CVE that no one has ever exploited may be less pressing than a medium one
  under active attack.

The [**EPSS**](https://www.first.org/epss/) (Exploit Prediction Scoring System) score
captures exploitability: it estimates the probability, from 0% to 100%, that a CVE will be
exploited in the wild within the next 30 days. Combining severity with EPSS helps you
prioritize — patch the vulnerabilities that are both damaging and likely to be used, first.

`jd image vulnerabilities` surfaces the CVEs found in an image, with severity and, when the
scanner provides it, an EPSS column:

```bash
# For templates that declare a jupyterlab image
jd image vulnerabilities --name jupyterlab
```

## Scanning images on AWS

Detecting CVEs requires a **scanner** that inspects an image's layers against vulnerability
databases. On AWS, images built by the official templates are stored in
[Amazon ECR](https://docs.aws.amazon.com/AmazonECR/latest/userguide/what-is-ecr.html), which
offers two scanning modes:

- **ECR basic scanning** — the default. Covers operating-system package CVEs only, and scans
  once: at the time `jupyter-deploy` pushes your image to ECR. It does not provide EPSS scores.
- **Amazon Inspector (enhanced scanning)** — account-level scanning that covers OS packages
  **and** language packages (including Python/pip) continuously re-scans images as new CVEs
  are disclosed, and provides EPSS scores.

`jd image vulnerabilities` auto-detects which mode is active and reports its findings — no
change to your project is needed.

```{note}
The language-package coverage matters for application images. It can catch CVEs in
the core software you run and in its transitive dependencies, which basic scanning
misses entirely. We therefore **recommend enabling Amazon Inspector** enhanced scanning.
```

### Enabling Amazon Inspector

Enhanced scanning is an **account-level** setting: enabling it turns scanning on for **all**
ECR repositories in the account and region, and it carries a per-image cost. Enable it once per account
with the AWS CLI:

```bash
aws inspector2 enable --resource-types ECR
```

Or in the AWS console: open **Amazon Inspector**, then activate it and select **Amazon ECR** as a
scanned resource type.

Pricing is per scanned image and varies by AWS region, see the
[Amazon Inspector pricing page](https://aws.amazon.com/inspector/pricing/) for current rates.

Once enabled, `jupyter-deploy` picks up Inspector reports automatically whenever you run
`jd image vulnerabilities`, including the EPSS column.
