# Red-CI demo: intentional lint regression — DO NOT MERGE to 027-cicd-hardening.
# Triggers ruff F401 (unused import) so backend-lint fails → all_passed=false.
import ast
