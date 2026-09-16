---
name: update-changelog
description: Add or update entries in CHANGELOG.md so they read consistently — after implementing a change, when checking the changelog before a release, or when catching up entries that were missed. Use whenever CHANGELOG.md needs editing.
---

# Update the changelog

Entries go under `## [Unreleased]` in `CHANGELOG.md`. Read that section first: it may already
cover what you are about to add, and it may be missing things that already landed.

## Write the entry

This is the whole job right after implementing a change, and it works on any branch.

- One line per user-visible change, under the right Keep a Changelog `### Category` heading —
  `Added`, `Changed`, `Fixed`, `Removed`, `Deprecated` or `Security`. Create the heading if it is
  not already there.
- Prefix breaking changes and removals with `_BREAKING_:`.
- Skip Dependabot bumps and CI- or workflow-only changes with no user-visible effect.
- Link the issue or PR number, and wrap to match the entries around it:

  ```
  - Description of the change. [#NNN](https://github.com/lasp/space_packet_parser/issues/NNN)
  ```

## Find entries that are missing

For the check before a release, or to catch up after entries were skipped. Run this on an
up-to-date `main` — on another branch, or one behind `origin/main`, it covers the wrong commits:

```bash
git fetch origin --tags
# Skip prerelease tags: `--sort=-version:refname` ranks 6.0.0rc4 above 6.0.0.
LATEST_TAG=$(git tag --sort=-version:refname | grep -E '^[0-9]+\.[0-9]+(\.[0-9]+)?$' | head -1)
git log --oneline --cherry-mark --left-right "$LATEST_TAG"...HEAD
```

Skip anything marked `=`. A release is tagged on its `release/X.Y` branch, so a fix cherry-picked
onto one ships under a different SHA than its copy on `main`, and `=` is what catches that. Keep
merge commits — their subjects carry the PR numbers.

Write up whatever is not already in `[Unreleased]`, following the rules above. Before a release,
finding nothing is the expected result. While you are here, if the footer `[unreleased]` link does
not compare from `$LATEST_TAG`, update it to `.../compare/LATEST_TAG...HEAD`.

## Convert `[Unreleased]` into a release section

Only once the version has been bumped for a release. Read the version from all three metadata
files: `pyproject.toml` (`[project]` `version`), `meta.yaml` (`package:` → `version:`) and
`CITATION.cff` (`version:`). The three must agree; if they do not, stop and tell the user. If that
version is already the latest tag, there is nothing to convert.

Otherwise use `AskUserQuestion` to confirm: "Version X.Y.Z is in
pyproject.toml/meta.yaml/CITATION.cff but the latest tag is LATEST_TAG. Is this a new release that
should get its own versioned section?" Convert only on a yes, and call that version `NEW_VERSION`.

Rename `## [Unreleased]` to `## [NEW_VERSION] - YYYY-MM-DD` (today) and add an empty
`## [Unreleased]` above it. Then fix the footer links, which are easy to get wrong. Replace the
existing `[unreleased]` line with the first of these and insert the second directly below it,
keeping the versioned links in descending order:

```
[unreleased]: https://github.com/lasp/space_packet_parser/compare/NEW_VERSION...HEAD
[NEW_VERSION]: https://github.com/lasp/space_packet_parser/compare/LATEST_TAG...NEW_VERSION
```
