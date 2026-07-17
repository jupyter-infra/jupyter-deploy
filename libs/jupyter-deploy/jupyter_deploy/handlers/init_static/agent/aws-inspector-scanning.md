By default ECR uses basic scanning, which has no EPSS scores. For richer reports, enable
Amazon Inspector enhanced scanning once per account and region (per-image cost applies):

```bash
aws inspector2 enable --resource-types ECR
```

`jd image vulnerabilities` then picks up Inspector findings automatically, adding EPSS.
