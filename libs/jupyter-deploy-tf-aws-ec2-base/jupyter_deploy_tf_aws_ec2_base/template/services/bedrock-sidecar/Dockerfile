# The AWS CLI is the whole program; refresh.sh drives `sts assume-role` on a timer.
FROM public.ecr.aws/aws-cli/aws-cli:latest

COPY refresh.sh /refresh.sh
RUN chmod 755 /refresh.sh

# Replaces the image's default `aws` entrypoint with the refresh loop.
ENTRYPOINT ["/refresh.sh"]
