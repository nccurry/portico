# Release process

Portico uses Semantic Versioning. A stable `1.x` release keeps its documented settings, Task commands, sheet requirements, and container commands compatible.

## Prepare a release

1. Create a release branch from `main`.
2. Update the version in `pyproject.toml`.
3. Move the Unreleased changelog entries to a dated version section.
4. Run `task privacy:check`, `task lint`, and `task test` from a clean worktree.
5. Merge the release change into `main`.

## Publish a release

1. Create an annotated tag named `vX.Y.Z` on the release commit.
2. Push the tag to GitHub.
3. Make sure that the GitHub Release and GHCR image use the same version after
   container publishing is added.

Do not reuse or move a published version tag. If a release is bad, fix the problem and publish a new patch version.
