Images are the container images this template builds for its applications and pushes to an
image registry. You address an image by `--name`; `jd image list` reports the images this
template defines.

```bash
# list the images declared by this template
jd image list

# check whether an image has been built and pushed to its registry (available/missing)
jd image status --name IMAGE-NAME
```

`jd image show` prints the registry location, the current tag, and the scanner backing
vulnerability reporting. `jd image tags` lists the tags available in the registry with
their push time and digest.

```bash
jd image show --name IMAGE-NAME
jd image tags --name IMAGE-NAME
```

`jd image vulnerabilities` reports the HIGH and CRITICAL findings the scanner detected for
an image. It uses the currently deployed tag unless you pass `--tag`. The EPSS column is
the Exploit Prediction Scoring System probability (0–100%) that a CVE will be exploited
within 30 days — higher is more urgent; it shows `n/a` for scanners that do not provide it
(e.g. basic registry scanning).

```bash
# vulnerabilities for the deployed tag
jd image vulnerabilities --name IMAGE-NAME

# vulnerabilities for a specific tag
jd image vulnerabilities --name IMAGE-NAME --tag TAG
```
