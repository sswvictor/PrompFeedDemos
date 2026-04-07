# CI Guardrails and Branch Protection

This document defines the required CI gate and GitHub branch protection settings for `main`.

## CI guardrails (implemented)
Workflow: `.github/workflows/ci.yml`

Required jobs:
- `repo-guardrails`
- `backend-check`
- `frontend-build`

`repo-guardrails` blocks:
- unresolved merge markers in tracked source/docs files
- missing required developer scripts used by local and CI workflows

`backend-check` blocks:
- backend dependency or compile errors
- migrations failing on a fresh database
- schema revision drift vs Alembic head

`frontend-build` blocks:
- frontend dependency or production build failures

## GitHub branch protection checklist (`main`)
Enable these settings in GitHub:

1. Require a pull request before merging
2. Require approvals: minimum 1 (recommended 2)
3. Dismiss stale approvals when new commits are pushed
4. Require review from code owners (if `CODEOWNERS` is used)
5. Require status checks to pass before merging
6. Required checks:
   - `repo-guardrails`
   - `backend-check`
   - `frontend-build`
7. Require branches to be up to date before merging
8. Require conversation resolution before merging
9. Restrict direct pushes to `main`
10. Optional but recommended: require signed commits

## Operational merge policy
- No direct pushes to `main` from exploratory work
- Every schema change must include migration + CI pass
- Every runtime flow change must include related script updates
- If a script is intentionally not updated, document why in PR notes
