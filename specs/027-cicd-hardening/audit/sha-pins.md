# SHA-Pin Lookup Table — Spec 27 CI/CD Hardening (T020, FR-008a)

Resolved via `gh api repos/<owner>/<action>/commits/<tag> --jq .sha` on 2026-04-17T18:06:59Z.
Each `uses:` line across `.github/workflows/` must reference the 40-char SHA with a trailing
`# vX.Y.Z` comment (Dependabot convention — research.md §8). Latest-in-major semver is the
version that the floating major tag (e.g. `v4`) resolved to at lookup time.

## Currently referenced in workflows (Wave 1 scope)

| Action | Tag requested | 40-char SHA | Latest-in-major |
|---|---|---|---|
| `actions/checkout` | v4 | `34e114876b0b11c390a56381ad16ebd13914f8d5` | v4.3.1 |
| `actions/setup-python` | v5 | `a26af69be951a213d495a4c3e4e4022e16d87065` | v5.6.0 |
| `actions/setup-node` | v4 | `49933ea5288caeca8642d1e84afbd3f7d6820020` | v4.4.0 |
| `actions/setup-go` | v5 | `40f1582b2485089dde7abd97c1529aa768e1baff` | v5.6.0 |
| `actions/cache` | v4 | `0057852bfaa89a56745cba8c7296529d2fc39830` | v4.3.0 |
| `actions/upload-artifact` | v4 | `ea165f8d65b6e75b540449e92b4886f43607fa02` | v4.6.2 |
| `docker/build-push-action` | v6 | `10e90e3645eae34f1e60eeb005ba3a3d33f178e8` | v6.19.2 |
| `docker/login-action` | v3 | `c94ce9fb468520275223c153574b00df6fe4bcc9` | v3.7.0 |
| `docker/metadata-action` | v5 | `c299e40c65443455700f0fdfc63efafe5b349051` | v5.10.0 |
| `docker/setup-buildx-action` | v3 | `8d2750c68a42422c14e847fe6c8ac0403b4cbd6f` | v3.12.0 |
| `dorny/paths-filter` | v3 | `d1c1ffe0248fe513906c8e24db8ea791d46f8590` | v3.0.3 |
| `github/codeql-action/init` | v3 | `ce64ddcb0d8d890d2df4a9d1c04ff297367dea2a` | v3.35.2 |
| `github/codeql-action/analyze` | v3 | `ce64ddcb0d8d890d2df4a9d1c04ff297367dea2a` | v3.35.2 |
| `goreleaser/goreleaser-action` | v6 | `e435ccd777264be153ace6237001ef4d979d3a7a` | v6.4.0 |
| `softprops/action-gh-release` | v2 | `3bb12739c298aeb8a4eeaf626c5b8d85266b0e65` | v2.6.2 |

## Forward-looking (A4 Wave 2, A6 Wave 3, A7 Wave 3) — resolved now to avoid duplicate lookups

| Action | Tag requested | 40-char SHA | Wave/Agent |
|---|---|---|---|
| `dtolnay/rust-toolchain` | stable | `29eef336d9b2848a0b548edc03f92a220660cdb8` | Wave 2 / A4 |
| `sigstore/cosign-installer` | v3 | `398d4b0eeef1380460a10c8013a76f728fb906ac` | Wave 3 / A6 |
| `aquasecurity/trivy-action` | master | `876cf04c63f65e9799bcf1043b584e72469c7143` | Wave 3 / A6 |
| `anchore/sbom-action` | v0 | `e22c389904149dbc22b58101806040fa8d37a610` | Wave 3 / A6 |
| `amannn/action-semantic-pull-request` | v5 | `e32d7e603df1aa1ba07e981f2a23455dee596825` | Wave 3 / A7 |
| `codecov/codecov-action` | v5 | `75cd11691c0faa626561e295848008c8a7dddffe` | Wave 3 / A7 |
| `pre-commit/action` | v3.0.1 | `2c7b3805fd2a0fd8c1884dcaebf91fc102a13ecd` | Wave 3 / A7 |
| `pnpm/action-setup` | v4 | `b906affcce14559ad1aafd4ab0e942779e9f58b1` | Wave 3 / A7 |

## Runtime pins (full semver — T023, FR-008c)

| Runtime | Pinned value | Source |
|---|---|---|
| Python | `3.14.4` | `gh api repos/python/cpython/releases` — latest v3.14 patch |
| Node | `22.22.2` | `gh api repos/nodejs/node/releases` — latest v22 LTS patch |
| Go | `1.25.4` | `gh api repos/golang/go/git/refs/tags` — latest go1.25 patch |
| Rust | `1.93.1` | A4 Wave 2 sets via `dtolnay/rust-toolchain@<sha>` — NOT in A2 scope |

## Tool pins

| Tool | Version | Location |
|---|---|---|
| `golangci-lint` | v2.11.4 | `.github/workflows/ci-cli.yml` install-from-source step (PR #2 pattern preserved) |

## Notes

- **Dependabot contract (research.md §8)**: trailing `# vX.Y.Z` comment is MANDATORY on every SHA-pinned `uses:`. Dependabot parses the comment to compute update PRs and rewrites BOTH the SHA and the comment on bump.
- **`github/codeql-action/init` and `.../analyze`** share the same repo — same SHA applies to both sub-actions.
- **`aquasecurity/trivy-action`** only publishes rolling `master` ref — pin the SHA; trailing comment becomes `# master (2026-04-17)` to signal that Dependabot will track the branch head.
- **`dtolnay/rust-toolchain@<sha>`** — Rust toolchain itself is pinned via `toolchain: 1.93.1` argument (A4's job); the ACTION SHA is what T020/T021 resolves.
- Any action added in later waves MUST be resolved via `gh api` before committing. Re-run this table if the wave 2/3 tags diverge from the values above.
