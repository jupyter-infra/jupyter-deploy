"""Constants for E2E test ordering.

Test Execution Order
====================

E2E tests run in the following sequence:

1. **Deployment test** (order=1):
   - Initial deployment and setup

2. **Mutating tests** (order >= 10):
   - Run in specific order with controlled dependencies
   - Each group starts at base + (group_number * 10)

3. **Non-ordered tests** (no order marker):
   - Run LAST, after all ordered tests (pytest-order default behavior)
   - Cover: application, config_set, host, open, org_and_teams, server, show,
     undeployed_project, users, utils

Note: pytest-order executes tests with positive ordinals before unordered tests.
"""

# Deployment test - runs first
ORDER_DEPLOYMENT = 1

# Mutating tests - run after deployment test, before non-ordered tests
# Base starting point for all mutating tests
_MUTATING_BASE = 10

# Group 1: External volumes tests
ORDER_EXTERNAL_VOLUMES = _MUTATING_BASE  # 10

# Group 2: Config apply tests
# reuse external volumes
ORDER_CONFIG_APPLY = _MUTATING_BASE + 10  # 20

# Group 3: GPU instance tests
# reuse external volumes
ORDER_GPU = _MUTATING_BASE + 20  # 30

# Group 4: Pixi package manager tests
# go uv -> pixi
ORDER_PIXI = _MUTATING_BASE + 30  # 40

# Group 5: UV package manager tests
# go pixi -> uv
ORDER_UV = _MUTATING_BASE + 50  # 50
