# Self-signed cert-pin transport.
#
# The instance generates a long-lived self-signed cert + private key at boot, persists
# them on the EBS data volume (survives stop/start), and publishes ONLY the public PEM to
# this SSM parameter via ssm:PutParameter. `jd proxy connect-info` reads the parameter live
# and hands the PEM to the client proxy as the pin target (load_verify_locations, with
# check_hostname disabled — the pin is on the cert, not the address).
#
# Terraform owns the parameter's identity (a stable name) but NOT its value: it seeds a
# placeholder and ignores subsequent value changes, so the real PEM never lands in state
# and no apply-time wait for cert generation is needed.
resource "aws_ssm_parameter" "cert_pin" {
  name        = "/jupyter-deploy/${local.doc_postfix}/cert-pin"
  description = "Public PEM of the instance self-signed cert; written by the instance at boot."
  type        = "String"
  tier        = "Standard" # one self-signed RSA-2048 leaf PEM (~1.2 KB) fits the 4 KB Standard limit
  value       = "placeholder-overwritten-by-instance-at-boot"
  tags        = local.combined_tags

  lifecycle {
    ignore_changes = [value]
  }
}
