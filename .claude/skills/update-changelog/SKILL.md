---
name: update-changelog
description: Add or update entries in CHANGELOG.md — a single entry for a change you just made, a catch-up across everything since the last release, or converting [Unreleased] into a versioned section. Use whenever CHANGELOG.md needs editing.
---

# Update the changelog

Read `CHANGELOG.md` first. Entries go under `## [Unreleased]` unless Step 4 applies, and
`[Unreleased]` is neither necessarily complete nor necessarily missing what you are about to add.

## Step 1 — Decide what to write up

- **A change you just made.** You already know what it is. Go to Step 2.
- **Everything since the last release.** Scan `main`. Run the scan on an up-to-date `main` — on
  another branch, or one behind `origin/main`, it covers the wrong commits, so say so and stop.

  ```bash
  git fetch origin --tags
  # Skip prerelease tags: `--sort=-version:refname` ranks 6.0.0rc4 above 6.0.0.
  LATEST_TAG=$(git tag --sort=-version:refname | grep -E '^[0-9]+\.[0-9]+(\.[0-9]+)?$' | head -1)
  git log --oneline --cherry-mark --left-right "$LATEST_TAG"...HEAD
  ```

  A release is tagged on its `release/X.Y` branch, so a fix cherry-picked onto one ships under a
  different SHA than its copy on `main`. Skip anything marked `=` — it is already released. Keep
  merge commits; Step 2 reads PR numbers out of their subjects.

## Step 2 — Write the entries

- Skip Dependabot bumps and CI/workflow-only changes with no user-visible effect.
- Skip anything already listed under `[Unreleased]`.
- Use the Keep a Changelog categories; prefix breaking changes and removals with `_BREAKING_:`.
- One line per change, linked to the issue or PR number:

  ```
  - Description of the change. [#NNN](https://github.com/lasp/space_packet_parser/issues/NNN)
  ```

## Step 3 — Add them under `## [Unreleased]`

Put each entry under the right `### Category` heading, creating headings as needed. If the footer
`[unreleased]` link does not compare from the latest release tag, update it to
`.../compare/LATEST_TAG...HEAD`.

Stop here unless you are preparing a release.

## Step 4 — Only when cutting a release

Release prep bumps the version before the changelog, so read it from all three metadata files:
`pyproject.toml` (`[project]` `version`), `meta.yaml` (`package:` → `version:`) and `CITATION.cff`
(`version:`). The three must agree; if they do not, stop and tell the user.

If that version is already the latest tag, there is nothing to convert and Step 3 was the whole job.
If it is ahead of the tag, use `AskUserQuestion` to ask "Version X.Y.Z is in
pyproject.toml/meta.yaml/CITATION.cff but the latest tag is LATEST_TAG. Is this a new release that
should get its own versioned section?" Convert only on a yes.

`NEW_VERSION` is that version. Rename `## [Unreleased]` to `## [NEW_VERSION] - YYYY-MM-DD` (today),
keeping its existing entries ahead of the new ones, and add an empty `## [Unreleased]` above it.
Then fix the footer links, which are easy to get wrong. Replace the existing `[unreleased]` line
with the first of these, and insert the second directly below it:

```
[unreleased]: https://github.com/lasp/space_packet_parser/compare/NEW_VERSION...HEAD
[NEW_VERSION]: https://github.com/lasp/space_packet_parser/compare/LATEST_TAG...NEW_VERSION
```

The new versioned link goes directly under `[unreleased]`, keeping versioned links in descending
order.
