---
name: update-changelog
description: Update CHANGELOG.md from the git history since the last release — add Keep a Changelog entries for unreleased PRs, or turn [Unreleased] into a versioned section when the version has been bumped. Use when asked to update, fill in, or catch up the changelog.
---

# Update the changelog

## Step 1 — Gather context

Run this on an up-to-date `main`: the commands below read the local `HEAD` and Step 4 edits the
local `CHANGELOG.md`. If the checkout is on another branch or behind `origin/main`, say so and stop.

```bash
git fetch origin --tags
# Skip prerelease tags: `--sort=-version:refname` ranks 6.0.0rc4 above 6.0.0.
LATEST_TAG=$(git tag --sort=-version:refname | grep -E '^[0-9]+\.[0-9]+(\.[0-9]+)?$' | head -1)
git log --oneline --cherry-mark --left-right "$LATEST_TAG"...HEAD
```

Read the markers, not just the subjects. `>` is on `main` only and is a candidate for an entry; `=`
means the same patch already shipped under `$LATEST_TAG` and must be skipped; `<` is on the tag side
only — a release-branch commit that never reached `main` — and is not yours to write up. A release
is tagged on its `release/X.Y` branch, so a fix cherry-picked onto one ships under a different SHA
than its copy on `main`, and `=` is what catches that. Keep merge commits — Step 3 reads PR numbers
out of their subjects.

Do not assume `[Unreleased]` is complete either — features have reached `main` without an entry.

Read `CHANGELOG.md` and the version in all three metadata files: `pyproject.toml` (`[project]`
`version`), `meta.yaml` (`package:` → `version:`) and `CITATION.cff` (`version:`). The three must
agree; if they do not, stop and tell the user.

## Step 2 — Pick the scenario

- **Version in the files differs from `LATEST_TAG`:** use `AskUserQuestion` to ask "Version X.Y.Z is
  in pyproject.toml/meta.yaml/CITATION.cff but the latest tag is LATEST_TAG. Is this a new release
  that should get its own versioned section?" Yes → Scenario A. No → Scenario B.
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

**Scenario A — new release.** `NEW_VERSION` is the version read from `pyproject.toml` in Step 1.
Rename `## [Unreleased]` to `## [NEW_VERSION] - YYYY-MM-DD` (today), keeping its existing entries
ahead of the new ones, and add an empty `## [Unreleased]` above it.
Then fix the footer links, which are easy to get wrong. Replace the existing `[unreleased]` line
with the first of these, and insert the second directly below it:

```
[unreleased]: https://github.com/lasp/space_packet_parser/compare/NEW_VERSION...HEAD
[NEW_VERSION]: https://github.com/lasp/space_packet_parser/compare/LATEST_TAG...NEW_VERSION
```

The new versioned link goes directly under `[unreleased]`, keeping versioned links in descending
order.

**Scenario B — unreleased only.** Add the entries under the right `### Category` headings in
`## [Unreleased]`, creating headings as needed. If the footer `[unreleased]` link does not compare
from `LATEST_TAG`, update it to `.../compare/LATEST_TAG...HEAD`.
