# Release process

Portico uses Semantic Versioning. A stable `1.x` release keeps its documented settings, Task commands, sheet requirements, and container commands compatible.

## Prepare a release

1. Create a release branch from `main`.
2. Update the version in `pyproject.toml`.
3. Move the Unreleased changelog entries to a dated version section.
4. Run `task privacy:check`, `task lint`, `task test`, and `task docs:check` from a clean worktree.
5. Merge the release change into `main`.

## Publish a release

1. Create an annotated tag named `vX.Y.Z` on the release commit.
2. Push the tag to GitHub.
3. Wait for the release workflow to finish.
4. Make sure that the GHCR version, major, minor, `latest`, and commit tags exist.
5. Make sure that the image has provenance, an SBOM, and an artifact attestation.

Do not reuse or move a published version tag. If a release is bad, fix the problem and publish a new patch version.

The workflow stops before publication when the tag does not match the version in
`pyproject.toml`. Delete an unpublished bad tag, correct the release commit, and
create the tag again. Do not delete or move a tag after its image is published.

## Protect main

Require pull requests for `main`. Use the aggregate `ci` job as the required
status check. The aggregate job covers native bootstrap checks, source checks,
coverage, privacy, documentation, and both container architectures.

## Publish the demo gallery

Before the first deployment, open the repository's **Settings > Pages** page and select **GitHub Actions** as the source. Each later push to `main` rebuilds and publishes the static gallery from the canonical logo and demo screenshots.
