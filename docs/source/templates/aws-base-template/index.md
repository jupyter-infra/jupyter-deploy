# AWS Base Template

The **AWS Base Template** deploys a **JupyterLab** application to a dedicated Amazon EC2 instance,
served on your domain with encrypted HTTPS, GitHub OAuth integration,
real-time collaboration, and fast UV-based environments.

The **AWS Base Template** is maintained and supported by AWS.

## 10k View

When you navigate to the application URL in your web browser, you connect to the EC2 instance over HTTPS. On the first visit, the instance redirects to GitHub for OAuth authentication; once verified, you connect to the `jupyter` container within your EC2 instance and see a **JupyterLab** application in your web browser.

![Overview](diagrams/overview.svg)

## Next Steps

```{toctree}
:maxdepth: 2

prerequisites
user-guide
architecture
bedrock-integration
details
```

## License

Licensed under the [MIT License](https://github.com/jupyter-infra/jupyter-deploy/blob/main/libs/jupyter-deploy-tf-aws-ec2-base/LICENSE).
