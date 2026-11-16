# Reponomics release infrastructure

Shared attestation workflows for Reponomics projects. Projects keep their own build, test and publication logic. The first consumer is [best-practices-mcp](https://github.com/reponomics/best-practices-mcp).

The reusable [attestation workflow](.github/workflows/attest.yml) downloads an artifact from the caller's current workflow run, generates build provenance or signs a supplied SBOM, and returns a signed bundle. It does not publish packages or releases. This is a SLSA Build Level 3-capable architecture under the integration conditions below; using the workflow alone does not establish a project's SLSA level.

## Interface

Call the reusable workflow as a job after a successful build, pinning it to a reviewed full commit SHA. The source job needs `contents: read`; the signing call needs `contents: read`, `id-token: write` and `attestations: write`. Keep workflow-level permissions read-only and grant signing permissions only on the calling job.

| Input | Meaning |
| --- | --- |
| `artifact-id` | One numeric artifact ID uploaded in the current caller workflow run. Cross-run or cross-repository downloads are not supported. |
| `subject-path` | Relative file path or glob inside that artifact, such as `dist/*`, `dist/*.whl` or `package.tar.gz`. Select between 1 and 1024 regular files. |
| `sbom-path` | Optional relative path to an SPDX or CycloneDX SBOM inside the same artifact. Leave empty for automatically generated SLSA build provenance. |
| `attestation-name` | Unique bundle name per workflow invocation, such as `provenance`, `runtime-wheel` or `runtime-sdist`. Use letters, digits, hyphens or underscores, beginning with a letter or digit, up to 80 characters. |

Paths use relative ASCII names containing letters, digits, underscores, hyphens, dots and slashes. Subject selectors additionally accept `*` and `?`. Absolute paths, empty components, `.`/`..` components, symlinks and output-injection characters are rejected. Selected filenames cannot contain wildcard characters. A supplied SBOM is data: signing it does not independently validate its description of the package.

The `attestations` output is the exact GitHub artifact ID containing `{attestation-name}.sigstore.json`. The upload is named `attestations-{run_id}-{run_attempt}-{attestation-name}` and retained for 30 days. Give separate calls unique names. Consumers should preserve signed bundles alongside releases for long-term availability.

The source workflow can call the signer once for provenance over all distributions and separately for each distribution's SBOM. It then downloads the exact output artifact IDs, verifies the packages and attestations against its expected identities, and publishes the unchanged packages and signed bundles. PyPI publication stays in the source workflow, preserving its Trusted Publisher registration and environment approval gate.

## Trust boundary and integration requirements

The signer runs in a fresh GitHub-hosted job. It executes only the fixed workflow code and SHA-pinned GitHub actions; it never checks out project source, runs downloaded files, restores a build cache, accepts arbitrary commands or signs a caller-provided provenance predicate. Caller inputs select artifact data only. GitHub's attestation action generates provenance using verified GitHub OIDC claims for the caller's workflow and source revision, and identifies the reusable signer separately.

[SLSA explicitly permits caller-generated artifact names and digests](https://slsa.dev/spec/v1.2/threats#build-threats). It does not require this signer to rebuild the software. GitHub's [build type](https://github.com/actions/buildtypes/blob/main/workflow/v1/README.md) describes the top-level caller workflow, while the reusable attestation workflow is its provenance generator. The SLSA project's [generic generator](https://github.com/slsa-framework/slsa-github-generator/blob/main/internal/builders/generic/README.md) provides precedent for keeping build logic in callers; new integrations should use supported GitHub attestations rather than that unmaintained generator.

Each consuming project must review its own release workflow against the [SLSA build requirements](https://slsa.dev/spec/v1.2/build-requirements):

- Build on ephemeral GitHub-hosted runners with no unrecorded remote influence or unsafe shared build caches. The signer cannot establish the isolation of earlier jobs merely by running on a hosted runner itself.
- Keep build-affecting choices in the versioned source and selected Git ref. The stock GitHub provenance action currently [omits manual workflow inputs](https://github.com/actions/toolkit/issues/2331). Do not accept arbitrary compiler flags, alternate source revisions or other unrecorded build controls while claiming complete Level 3 provenance. Derive release tags from the selected ref rather than a redundant manual input.
- Use supported top-level trigger types: `push`, `create`, `release` or `workflow_dispatch`. The signer fails closed on other source events, including pull-request workflows.
- Pin this workflow and actions by full SHA, protect the infrastructure repository, restrict its write access and review changes to the signer. A compromise of the signing implementation can compromise the claims it signs.
- Verify the exact package bytes, expected source repository and workflow path, source ref and SHA, reusable signer workflow and SHA, and OIDC issuer before publication. Keep expected values independently of downloaded manifests. A signature from an unexpected source or signer must fail.
- Preserve provenance for consumers. Qualify the first integration with positive verification and rejection of modified bytes, unexpected source identity and unexpected signer identity before making a release-level claim.

`--deny-self-hosted-runners` verifies the environment of the attestation-generating job. It does not prove that all preceding caller build jobs used hosted runners. Source workflow review remains necessary.

## Verification

Use the source repository as the attestation lookup scope, and this repository as the signer. Replace placeholders with independently trusted release metadata:

```sh
gh attestation verify PATH_TO_DISTRIBUTION \
  --repo SOURCE_OWNER/SOURCE_REPOSITORY \
  --signer-workflow reponomics/release-infrastructure/.github/workflows/attest.yml \
  --signer-digest REVIEWED_SIGNER_COMMIT \
  --source-ref refs/tags/RELEASE_TAG \
  --source-digest SOURCE_COMMIT \
  --cert-oidc-issuer https://token.actions.githubusercontent.com \
  --deny-self-hosted-runners \
  --format json
```

Also check the verified provenance's `buildDefinition.externalParameters.workflow.path` against the expected source release workflow, and its repository against the expected source repository. For SBOMs, require the corresponding predicate type. The source repository remains the lookup scope even though the signer is external. See [GitHub CLI verification](https://cli.github.com/manual/gh_attestation_verify).

## Review and activation

1. Review and merge this repository's workflow PR. Preserve any reviewed commit already pinned by consumers with a merge commit; if squashed or rebased, update consumer pins to the resulting reviewed SHA.
2. Keep default-branch protections active: pull requests, required checks, resolved conversations, no force-push or deletion, and no bypass actors. Zero approvals currently accommodate the sole maintainer; add required independent review when maintainership expands. Default Actions permissions remain read-only and Actions cannot approve pull requests.
3. Review each source integration and its project-specific build isolation, input and verification policies. Confirm organization Actions policy permits this public reusable workflow.
4. Run qualification without publishing a package. A synthetic signing test demonstrates the attestation and verification path; it does not demonstrate a production build or publication.
5. Execute the first real candidate through the source project's approval and publication process, and verify the resulting published artifacts before claiming that release's SLSA level.

## Development

Python 3.11 or newer is required. Run `make setup`, then `make check` with `actionlint` available on PATH. Tests cover unsafe artifact identifiers, path traversal, symlinks, output injection, missing files and workflow privilege boundaries. CI builds the pinned workflow linter and checks every workflow.

The repository originally adapted release tooling from best-practices-mcp v0.5.0 under the MIT license. See [LICENSE](LICENSE).
