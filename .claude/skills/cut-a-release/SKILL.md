---
name: cut-a-release
description: Cut a release of space_packet_parser — create the release branch, bump the version in all three metadata files, finalize the CHANGELOG, open the release PR, and tag. Use when asked to cut, prepare, or publish a release.
---

# Cut a release

The authoritative process lives in [`docs/source/developers.md`](../../../docs/source/developers.md)
under "Release Process". This skill is the operational version of it, plus the repo-specific traps
that are easy to hit. If the two ever disagree, `developers.md` wins — and fix this file. The single exception is
flagged inline in Step 7.

Releases are published by a GitHub Actions workflow that fires when a tag matching the release
pattern is pushed (`.github/workflows/release.yml`), not on merges. Nothing is published until a tag
is pushed. The workflow does not check whether the tag is annotated — annotated (and signed) tags are
a process requirement enforced by this skill, not something the workflow verifies (see Step 7).

## Step 1 — Work out what is actually unreleased

**Trap: `git log <latest-tag>..HEAD` lies in this repo.** Release tags are made on long-lived
`release/X.Y` branches, so the tagged commit is not the tip of `main` and the range includes commits
that were already released via a cherry-pick, under a different SHA. Ancestry checks
(`git merge-base --is-ancestor`) can't catch this — every commit in that range is by definition not
an ancestor of the tag, so the check always says "unreleased". Compare patch content instead:

```bash
git fetch origin --tags
LATEST_TAG=$(git tag --sort=-version:refname | grep -E '^[0-9]+\.[0-9]+\.[0-9]+$' | head -1)
# For a patch release on an existing release/X.Y line, anchor the grep to that prefix instead
# (e.g. `grep -E '^6\.1\.'`), so LATEST_TAG can't jump ahead to a newer, already-branched release.

git log --cherry-pick --right-only "$LATEST_TAG...HEAD" --oneline --no-merges
```

This lists only commits on `HEAD` with no patch-equivalent already on `$LATEST_TAG` — the genuinely
unreleased ones.

**Then reconcile against `CHANGELOG.md`.** Do not trust the `[Unreleased]` section to be complete —
features do land on `main` without a changelog entry. Grep for each unreleased PR's subject matter
before assuming it is recorded. Read the actual diff (`git show --stat <sha>`, then the diff of the
source files) for anything undocumented, because you need to classify it correctly and because it
may change the version number.

## Step 2 — Decide the version number, and ask

Version numbers are PEP 440. Major = breaking API change, minor = non-breaking features,
patch = bugfixes.

**This is the maintainer's call, not yours.** Present the evidence and ask before proceeding:

- every unreleased feature (drives minor at minimum),
- every behavior change that could break a caller, with its blast radius,
- your recommendation and its reasoning.

Also ask whether they want a TestPyPI dry run first (see Step 7).

## Step 3 — Create the release branch

Named for major and minor only — the patch is dropped so bugfix releases can be made on the same
branch later.

```bash
git checkout main && git pull
git checkout -b release/X.Y
```

For a patch release on an existing line, check out the existing `release/X.Y` instead of creating one.

## Step 4 — Bump the version in all three metadata files

The version is duplicated in three places and they must match exactly:

| File             | Field                       |
| ---------------- | --------------------------- |
| `pyproject.toml` | `version` under `[project]` |
| `CITATION.cff`   | `version`                   |
| `meta.yaml`      | `version` under `package`   |

There is no `__version__` in the package source — the version is read from package metadata, so
these three files are the whole job.

`scripts/check_metadata.py` runs as an `always_run` pre-commit hook and verifies that the name,
description, and version all agree across the three files. It is your safety net here, but run it
deliberately rather than discovering a mismatch at commit time:

```bash
pre-commit run check-space-packet-parser-metadata --all-files
```

## Step 5 — Finalize the CHANGELOG

Add any entries you found missing in Step 1 first, then promote the section:

1. Add missing entries under the correct Keep a Changelog heading in `[Unreleased]`
   (`Security` / `Added` / `Changed` / `Deprecated` / `Removed` / `Fixed`), each ending with a
   `[#NNN](https://github.com/lasp/space_packet_parser/issues/NNN)` link when there is a tracked issue
   or PR — not every entry has one (see the existing entries around `CHANGELOG.md:97-107`).
2. Rename `## [Unreleased]` to `## [X.Y.Z] - YYYY-MM-DD` using today's date.
3. Insert a new, empty `## [Unreleased]` heading above it.
4. Update the footer diff links at the bottom of the file:
   ```
   [unreleased]: https://github.com/lasp/space_packet_parser/compare/X.Y.Z...HEAD
   [X.Y.Z]: https://github.com/lasp/space_packet_parser/compare/PREV_TAG...X.Y.Z
   ```
   Versioned links stay in descending order.

Prettier runs on markdown with the default `proseWrap: preserve`, so your manual line wrapping is
kept. Match the surrounding entries, which wrap at roughly 100 characters.

Then revisit `README.md`. It carries no version string today, so usually there is nothing to do —
but check that nothing it claims was invalidated by this release.

## Step 6 — Verify, commit, and open the release PR

```bash
pre-commit run --all-files
uv run pytest tests
uv build --out-dir /tmp/dist   # confirm the artifacts carry the new version
```

Commit and push. Commits in this repo are **GPG signed** (`commit.gpgsign=true`); never reach for
`--no-gpg-sign`. If signing fails in the devcontainer it is almost always the forwarded gpg-agent
socket having died — the key lives on the host, not in the container. Hand that back to the user to
fix rather than working around it. Confirm the signature took:

```bash
git log --format='%G? %h %s' -1   # want a leading G
```

Open a PR from `release/X.Y` into `main`. Per `developers.md`, this PR exists to show the team how
the release is progressing while the branch is polished — it is **not** what publishes the release.
Fill out `.github/pull_request_template.md`, and call out any behavior change that a reviewer might
think deserves a bigger version bump.

If `main` moves while the PR is open, rebase the release branch onto it and resolve conflicts.

## Step 7 — Tag to publish

Only once the maintainer is satisfied with the branch. The tag must be annotated **and signed**.

```bash
git checkout release/X.Y && git pull
git tag -s X.Y.Z -m "Version X.Y.Z"
git push origin X.Y.Z
```

> **Deliberate deviation from `developers.md`.** The docs say `git tag -a`, which produces an
> _unsigned_ tag, but every release tag since `6.0.0rc3` is signed. `-s` here is correct and is the
> one place this skill knowingly departs from the docs — do not "fix" it back to `-a`. Tracked in
> [issue #279](https://github.com/lasp/space_packet_parser/issues/279); once that lands, the docs
> and this file agree again and this note can go. Note that `commit.gpgsign` does not sign tags —
> that needs `tag.gpgsign` or an explicit `-s`, which is how the two drifted apart.

For a TestPyPI dry run, prefix the tag with `test-release/`. This publishes to TestPyPI only and
skips the public PyPI — but `create-github-release` has no guard for `test-release/` tags, so a
GitHub Release (marked prerelease) is still created.

The workflow builds from whatever is checked out at the tag, so the artifact version comes from the
three metadata files (Step 4), not the tag name. Bump them to `X.Y.Zrc1` and commit before tagging the
dry run, then revert to plain `X.Y.Z` before Step 7's real tag below:

```bash
# bump pyproject.toml / CITATION.cff / meta.yaml to X.Y.Zrc1 (per Step 4), commit, then:
git tag -s test-release/X.Y.Zrc1 -m "Test Release Candidate X.Y.Zrc1"
git push origin test-release/X.Y.Zrc1

# revert the three metadata files back to X.Y.Z before tagging the real release below
```

Pushing the tag is the irreversible, outward-facing step — PyPI releases cannot be replaced.
**Always confirm with the user immediately before pushing a tag.**

The workflow in `.github/workflows/release.yml` then builds the PyPI and Conda artifacts, publishes
to PyPI (or TestPyPI), pushes the Conda package to the `lasp` Anaconda channel, and creates a GitHub
Release with auto-generated notes.

A tag is marked as a **full release** only if it matches `^[0-9]+\.[0-9]+\.[0-9]+$`. Anything with a
suffix (`6.2.0rc1`) is marked a prerelease — but note that a suffixed tag without the
`test-release/` prefix still publishes to the **public** PyPI.

## Step 8 — Merge back into main

The release branch is long-lived; it is not deleted. Merge the PR from Step 6 so the version bump
and the finalized changelog land on `main` and are carried into the next release.

## Watch out for

- **Don't commit to `main`.** A `no-commit-to-branch` pre-commit hook blocks commits to `main` and
  `dev`. All release work happens on `release/X.Y`.
- **The changelog is not self-maintaining.** Step 1's reconciliation against git history is the
  point of this process, not a formality. The 6.2.0 release found an entire feature (XTCE `UnitSet`
  support, issue #47) that had shipped to `main` unrecorded.
- **Release notes on GitHub are generated from commit messages** since the last non-prerelease
  release, independently of `CHANGELOG.md`. The changelog is for humans reading the repo; both matter.
- **Expect the generated release notes to over-report**, and don't try to fix it. They are built by
  walking commits from the previous tag, and because that tag sits on a `release/X.Y` branch holding
  only cherry-picked fixes, everything that landed on `main` in the meantime looks new — so PRs
  already shipped in earlier patch releases get listed again. This is the same topology quirk as the
  Step 1 trap. The `Full Changelog` compare link is still correct, and `CHANGELOG.md` is the accurate
  record. The 6.2.0 notes listed PRs back to #234 for this reason.
- The related [`update-changelog`](../update-changelog/SKILL.md) skill handles routine changelog
  maintenance between releases.
