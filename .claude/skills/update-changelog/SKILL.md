Update `docs/source/changelog.md` based on recent git history. Follow these steps exactly.

## Step 1 — Gather context

Run the following commands:

```bash
git tag --sort=-version:refname | head -1
```

Save the output as `LATEST_TAG`. Then run:

```bash
git log <LATEST_TAG>..HEAD --oneline --no-merges
git log <LATEST_TAG>..HEAD --oneline --merges
```

Read these files in full:

- `docs/source/changelog.md`
- `pyproject.toml` (find `version =` under `[project]`)
- `meta.yaml` (find `version:` field)
- `CITATION.cff` (find `version:` field)

## Step 2 — Detect release scenario

Compare the version in `pyproject.toml` / `meta.yaml` / `CITATION.cff` against `LATEST_TAG`.

- If the version in the files **differs** from `LATEST_TAG`, use `AskUserQuestion` to confirm:
  > "Version X.Y.Z appears in pyproject.toml/meta.yaml/CITATION.cff but the latest git tag is LATEST_TAG. Is this a new release that should be added as a versioned section in the changelog?"
  - If the user confirms → **Scenario A** (new release)
  - If the user declines → **Scenario B** (update unreleased only)
- If the version already matches `LATEST_TAG` → **Scenario B** automatically.

## Step 3 — Analyze git log

From the combined output of both `git log` commands:

- Identify meaningful changes. Look for PR numbers via patterns `(#NNN)` or `Merge pull request #NNN`.
- **Skip**: pure Dependabot dependency bumps (e.g. "Bump X from Y to Z"), CI/workflow-only changes with no user-visible impact.
- Classify each meaningful change into one of these Keep A Changelog categories:
  - `Added` — new features or capabilities
  - `Changed` — changes to existing behavior; prefix `_BREAKING_:` for breaking changes
  - `Fixed` — bug fixes
  - `Removed` — removed features or APIs; prefix `_BREAKING_:` for breaking removals
  - `Deprecated` — features marked for future removal
  - `Security` — security fixes
- Format each entry as:
  ```
  - Description of the change. [#NNN](https://github.com/lasp/space_packet_parser/issues/NNN)
  ```
- Check the existing `## [Unreleased]` section in the changelog — do **not** duplicate entries already present there.

## Step 4 — Edit the changelog

### Scenario A — New release (user confirmed)

Let:

- `NEW_VERSION` = version from `pyproject.toml`
- `TODAY` = today's date in `YYYY-MM-DD` format
- `PREV_TAG` = `LATEST_TAG`

1. Rename the `## [Unreleased]` heading to `## [NEW_VERSION] - TODAY`. Populate its body with the categorized entries from Step 3, preserving any entries that were already in `[Unreleased]` before them.
2. Insert a new empty `## [Unreleased]` section above the renamed section:

   ```markdown
   ## [Unreleased]

   ## [NEW_VERSION] - TODAY
   ```

3. Update the footer diff links at the bottom of the file:
   - Change the `[unreleased]` link to:
     ```
     [unreleased]: https://github.com/lasp/space_packet_parser/compare/NEW_VERSION...HEAD
     ```
   - Insert a new versioned link immediately after the `[unreleased]` line:
     ```
     [NEW_VERSION]: https://github.com/lasp/space_packet_parser/compare/PREV_TAG...NEW_VERSION
     ```

### Scenario B — Update unreleased only

1. Add the categorized entries from Step 3 under the appropriate `### Category` headings within the existing `## [Unreleased]` section. Create any missing `### Category` headings as needed.
2. Footer: if `[unreleased]` currently points to a tag other than `LATEST_TAG`, update it to:
   ```
   [unreleased]: https://github.com/lasp/space_packet_parser/compare/LATEST_TAG...HEAD
   ```

## Step 5 — Verify

After editing, confirm:

- `## [Unreleased]` is the first version section in the file.
- All new entries are under the correct `### Category` heading.
- The footer `[unreleased]` link ends with `...HEAD`.
- No duplicate entries exist.
- Footer versioned links are in descending version order.
