---
name: update-changelog
description: Update CHANGELOG.md from the git history since the last release — add Keep a Changelog entries for unreleased PRs, or turn [Unreleased] into a versioned section when the version has been bumped. Use when asked to update, fill in, or catch up the changelog, or while preparing a release.
---

# Update the changelog

## Step 1 — Gather context

```bash
git fetch origin --tags
LATEST_TAG=$(git tag --sort=-version:refname | head -1)
git log "$LATEST_TAG"..HEAD --oneline
```

**Trap: that range lists commits that already shipped.** Release tags live on long-lived
`release/X.Y` branches carrying cherry-picked fixes, so the tagged commit is not an ancestor of the
tip of `main` in the usual way. Before writing an entry for a commit, confirm it is unreleased:

```bash
git merge-base --is-ancestor <sha> "$LATEST_TAG" && echo "already released" || echo "unreleased"
```

Do not assume `[Unreleased]` is complete either — features have reached `main` without an entry.

Read `CHANGELOG.md` and the version in all three metadata files: `pyproject.toml` (`[project]`
`version`), `meta.yaml` (`version:`) and `CITATION.cff` (`version:`). The three must agree; if they
do not, stop and tell the user.

## Step 2 — Pick the scenario

- **Version in the files differs from `LATEST_TAG`:** ask the user "Version X.Y.Z is in
  pyproject.toml/meta.yaml/CITATION.cff but the latest tag is LATEST_TAG. Is this a new release that
  should get its own versioned section?" Yes → Scenario A. No → Scenario B.
- **Version matches `LATEST_TAG`:** Scenario B.

## Step 3 — Write entries

- Skip Dependabot bumps and CI/workflow-only changes with no user-visible effect.
- Skip anything already listed under `[Unreleased]`.
- Use the Keep a Changelog categories; prefix breaking changes and removals with `_BREAKING_:`.
- One line per change, linked to the issue or PR number found in the commit subject:

  ```
  - Description of the change. [#NNN](https://github.com/lasp/space_packet_parser/issues/NNN)
  ```

## Step 4 — Edit `CHANGELOG.md`

**Scenario A — new release.** Rename `## [Unreleased]` to `## [NEW_VERSION] - YYYY-MM-DD` (today),
keeping its existing entries ahead of the new ones, and add an empty `## [Unreleased]` above it.
Then fix the footer links, which are easy to get wrong:

```
[unreleased]: https://github.com/lasp/space_packet_parser/compare/NEW_VERSION...HEAD
[NEW_VERSION]: https://github.com/lasp/space_packet_parser/compare/LATEST_TAG...NEW_VERSION
```

The new versioned link goes directly under `[unreleased]`, keeping versioned links in descending
order.

**Scenario B — unreleased only.** Add the entries under the right `### Category` headings in
`## [Unreleased]`, creating headings as needed. If the footer `[unreleased]` link does not compare
from `LATEST_TAG`, update it to `.../compare/LATEST_TAG...HEAD`.
