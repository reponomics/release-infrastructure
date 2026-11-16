# Reponomics release infrastructure

Reviewed reusable build and attestation workflows for Reponomics releases. The first consumer is [best-practices-mcp](https://github.com/reponomics/best-practices-mcp). This repository is preparation for a hardened release path; it does not establish that any published release meets SLSA Build Level 3.

## Trust boundary

The reusable [Python release workflow](.github/workflows/python-release.yml) owns both the build and provenance generation. It accepts only a release tag and prerelease flag, allows only the canonical source repository's tagged `release.yml` dispatch, and checks out the caller's exact commit without persisted credentials. It does not accept a build command, artifact ID, digest, repository URL, or signing subject from its caller.

The build job has only `contents: read`. It runs the source project's existing conformance, qualification, SBOM, vulnerability and license checks, then uploads the candidate bundle. Project build scripts execute in this job and are not trusted with signing credentials. A separate GitHub-hosted job downloads that exact artifact ID, checks inventory, checksums and source identity, and signs the distributions and reference-installation SBOMs without checking out or executing project code. Only this second job receives `id-token: write` and `attestations: write`.

The caller pins this workflow by full commit SHA. Its separate `pypi` environment-gated job verifies the reusable signer workflow, signer commit, source tag and source commit before publishing the unchanged distributions. PyPI publication remains in the source repository because [PyPI currently does not support registering a reusable workflow as a Trusted Publisher](https://docs.pypi.org/trusted-publishers/troubleshooting/#reusable-workflows-on-github). No PyPI credentials or publisher registration are needed here.

Source-controlled Make targets, scan inputs and generated reports remain part of the source being built. Their presence does not independently enforce project quality against malicious source or certify SBOM accuracy. The protected boundary establishes build provenance and signing isolation, not that the source or its outputs are benign.

## Review and activation

1. Review and merge this repository's workflow PR. Preserve the reviewed commit in history; use a merge commit rather than squashing if the consumer already pins the feature commit. If rebased or squashed, update the consumer to the resulting reviewed full SHA.
2. Protect `main` and workflow ownership before using this as a trusted builder. Require pull requests and CODEOWNER approval, prevent force-push/deletion, restrict bypasses, and limit repository write access to release-infrastructure maintainers. The supplied CODEOWNERS file names the current maintainer; configure the appropriate team if governance expands.
3. Review the source integration PR and verify its full-SHA pin matches the reviewed workflow. Preserve the source repository's `pypi` approval gate and existing Trusted Publisher identity (`reponomics/best-practices-mcp`, `release.yml`, environment `pypi`). Check organization Actions policy permits this public reusable workflow.
4. Merge the source integration only when ready for its next release. Do not rerun an old tag expecting the new workflow; GitHub executes the workflow stored at that tag.
5. Qualify a new release through the complete build, attestation, approval, PyPI publication and consumer-verification path. Confirm the certificate identifies this reusable workflow and its pinned commit, as well as the source repository/tag/commit. Until then, describe this as an unqualified transition, not an achieved SLSA level.

Creating the repository and opening these PRs does not alter the existing publisher configuration or run a publication. The reusable workflow has no independent dispatch or push publication trigger.

## Verification

Use the source repository as the attestation lookup scope, and this repository as the signer. For example, replace all placeholders with independently trusted release metadata:

```sh
gh attestation verify PATH_TO_DISTRIBUTION \
  --repo reponomics/best-practices-mcp \
  --signer-workflow reponomics/release-infrastructure/.github/workflows/python-release.yml \
  --signer-digest REVIEWED_WORKFLOW_COMMIT \
  --source-ref refs/tags/RELEASE_TAG \
  --source-digest SOURCE_COMMIT \
  --deny-self-hosted-runners
```

See [GitHub's reusable-workflow SLSA guide](https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/increase-security-rating) and the [introductory attestation article](https://github.blog/enterprise-software/devsecops/enhance-build-security-and-reach-slsa-level-3-with-github-artifact-attestations/). Signed SBOMs describe the reference installations produced by the build, not every possible downstream dependency resolution.

## Development

Python 3.11 or newer is required. Run `make setup`, then `make check` (with `actionlint` available on PATH). Tests exercise rejected candidate mutations, foreign source identity, path traversal, symlinks, inventory mismatches and workflow privilege boundaries. CI also builds the pinned workflow linter and runs it against the workflow files. Every action is pinned to a full commit SHA; update pins only after review.

The initial workflow, verifier and associated tests were adapted from best-practices-mcp v0.5.0 under the MIT license. See [LICENSE](LICENSE).
