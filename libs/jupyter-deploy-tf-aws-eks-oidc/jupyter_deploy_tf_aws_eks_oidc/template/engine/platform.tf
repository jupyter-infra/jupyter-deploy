# --- Platform barrier ---
#
# Single-source-of-truth aggregator for the FULL platform layer that every workspace
# service (operator, router, workspace charts) sits on top of. It composes the EKS
# add-on barrier (null_resource.cluster_addons) with the optional platform layers
# defined in platform_*.tf files.
#
# Every service helm_release depends_on this instead of null_resource.cluster_addons,
# so on create the whole platform is up before any service starts, and on destroy every
# service uninstalls BEFORE any platform layer is removed. Adding a new platform layer
# (platform_keda.tf, platform_karpenter.tf, ...) is then a one-line change here — all
# downstream services inherit the ordering.
#
# Count-gated platform layers use a splat reference that resolves to an empty list when
# disabled, so toggling one off leaves this barrier equivalent to null_resource.cluster_addons.
resource "null_resource" "platform" {
  depends_on = [
    # Keep cluster_addons here, NOT just on the optional layers: the service releases
    # depend on this barrier INSTEAD of cluster_addons, so this is the only thing pinning
    # them after the EKS add-ons. Optional layers (fluent_bit) are count-gated and vanish
    # when disabled — if the add-on edge lived only through them, a flag-off deploy would
    # lose add-on ordering entirely and destroy would race coredns/ebs-csi/cert-manager
    # against the Helm uninstalls (operator dies mid-uninstall, finalizers hang).
    null_resource.cluster_addons,
    helm_release.cluster_autoscaler,
    helm_release.fluent_bit,
  ]
}