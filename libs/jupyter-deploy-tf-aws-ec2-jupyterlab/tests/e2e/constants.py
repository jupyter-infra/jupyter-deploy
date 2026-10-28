"""Shared constants for the jupyterlab E2E suite: test ordering, and the mutating pass fixtures.

Test Execution Order
====================

1. **Deployment test** (order=1) — verifies the app is reachable the moment `jd up` finishes.
2. **Mutating tests** (order >= 10) — in-place `jd up` cycles on the SAME deployment: the two
   instance swaps, the zone swap, then the Bedrock round trip.
3. **Non-ordered tests** — run LAST (pytest-order runs positive-ordinal tests first).

The mutating ordinals are load-bearing, not cosmetic: this suite deliberately mutates ONE
deployment in place rather than deploying one project per configuration, because the
transitions are the coverage — terraform replacing the instance under a persisted data
volume, the volume reattaching at boot, the package-manager environment rebuilding, the app
returning on the same pinned cert. Apply #2 (`pixi -> uv`) is only meaningful after apply #1
(`uv -> pixi` + GPU), so `-k test_mutating_cpu_uv` on its own is NOT a valid entry point.
Do not "optimize" these into two independent runs.
"""

# Deployment test — runs first
ORDER_DEPLOYMENT = 1

# Mutating tests — after the deployment test, before the non-ordered tests
_MUTATING_BASE = 10

# Apply #1: t3.medium + uv  ->  GPU + pixi + external EBS/EFS mounts + larger log retention
ORDER_MUTATING_GPU_PIXI = _MUTATING_BASE  # 10

# Apply #2: GPU + pixi  ->  CPU + uv (external volumes stay mounted)
ORDER_MUTATING_CPU_UV = _MUTATING_BASE + 10  # 20

# Apply #3: availability-zone swap with volume preservation (test_volume_swaps.py).
#
# LAST of the mutating applies, and unlike the two above it is genuinely runnable on its own: its
# fixture provisions the mounts it needs rather than inheriting them from apply #1. It is ordered last
# anyway because it leaves the deployment in a different zone, and because a zone swap is the most
# expensive thing in the suite -- a failure here should not cost the cheaper coverage.
ORDER_MUTATING_VOLUME_SWAPS = _MUTATING_BASE + 20  # 30

# Rides on apply #1 (no apply of its own): the coding agents must still answer on the pixi image
# right after the instance swap, i.e. the sidecar re-published credentials on the new instance.
# Shares ordinal 11 with test_run_gpu_notebook on purpose: both only need to follow apply #1, and
# alphabetical file order decides between them.
ORDER_CODING_AGENTS_AFTER_GPU_PIXI = ORDER_MUTATING_GPU_PIXI + 1  # 11

# Applies #4-#6 (test_coding_agents.py): Bedrock on -> off -> on with global inference scope ->
# back to the defaults. Each test applies its own change inline and the NEXT one is its restore,
# so there is no teardown `finally` and the chain is only valid run in this order. After the zone
# swap because these re-render the services only; a failure here must not cost the swap coverage.
ORDER_MUTATING_BEDROCK_OFF = _MUTATING_BASE + 30  # 40
ORDER_MUTATING_BEDROCK_GLOBAL = _MUTATING_BASE + 40  # 50
ORDER_MUTATING_BEDROCK_GEO = _MUTATING_BASE + 50  # 60

# --------------------------------------------------------------------------- mutating pass
# Shared by BOTH mutating files: apply #1 provisions the mounts and writes the flags, apply #2
# asserts they survived. They live here rather than in either test module so neither has to import
# the other -- the two applies are ordered peers, not a dependency.

# Flag written to the home volume BEFORE apply #1, so its survival proves the data volume
# reattached to a brand-new instance. The external-volume flags are written after apply #1
# (the volumes do not exist before it) and checked after apply #2.
HOME_FLAG = "e2e_flag_home.txt"
EBS_FLAG = "external-ebs1/e2e_flag_ebs.txt"
EFS_FLAG = "external-efs1/e2e_flag_efs.txt"

# Mount points the applies provision.
EBS_MOUNT = "name=ebs1,mount_point=external-ebs1,size_gb=50"
EFS_MOUNT = "name=efs1,mount_point=external-efs1"

# --------------------------------------------------------------------------- volume identities
# What `jd volume --name` takes: the mount path as the user sees it in the app, NOT the terraform
# resource name or the `name=` field of the mount spec. Derived from the mount points above so a
# renamed mount cannot leave these stale.
#
# `home` is also the DEFAULT --name, because it is the first entry of the manifest's `volumes.static`
# list. Asserted in test_volume.py rather than assumed.
HOME_VOLUME = "home"
EBS_VOLUME = f"{HOME_VOLUME}/external-ebs1"
EFS_VOLUME = f"{HOME_VOLUME}/external-efs1"
