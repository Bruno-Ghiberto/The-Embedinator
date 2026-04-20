# Red-CI demo: intentional lint regression — DO NOT MERGE to 027-cicd-hardening.
# Triggers ruff F821 (undefined name) so backend-lint fails → all_passed=false.
_ = _undefined_name_red_ci_demo  # F821: name never defined in this module
