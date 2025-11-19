# Developer Documentation

## Installing Development Dependencies

Install development dependencies using `uv`` with all the extras groups:

```bash
# Install uv if you haven't already
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies including optional extras
uv sync --all-extras
```

Note: `uv` is a fast, Rust-based Python package installer and resolver that is PEP-compliant and fully compatible with pip and PyPI.

Once the development dependencies are installed and the uv-generated `.venv` is activated, you can run

```bash
pre-commit install
```

to get pre-commit hooks to automatically run the linting and formatting checks for you before each commit.

## Testing

Testing is run with `pytest` and the order is randomized by `pytest-randomly`.
To run all tests, run

```bash
pytest tests
```

To run all tests in docker containers (tests against many versions of python), run

```bash
docker-compose up --build && docker-compose down
```

## Building Documentation with Sphinx

Documentation is automatically built on ReadTheDocs in response to every PR and release,
but you can also build it locally with:

```bash
# From docs directory
make html && open build/html/index.html
```

## Making a Pull Request

Feel free to fork this repo and submit a PR!

- If you are working on an issue, link your PR to that issue.
- All feature PRs should be destined for the `main` branch (trunk-based development).
- Reviews are required before merging and our automated tests must pass.
- Please fill out the PR template that is populated when creating a PR in the GitHub interface.

## Release Process

Releases are automatically created using a GitHub Actions workflow that responds to pushes of annotated git tags.

### Versioning

Version numbers must be PEP440 strings: https://peps.python.org/pep-0440/

That is,

```
[N!]N(.N)*[{a|b|rc}N][.postN][.devN]
```

#### Major Minor Patch Meanings

- **Major**: Breaking API change.
- **Minor**: Non-breaking features.
- **Patch**: Bugfixes.

### Preparing for Release

1. Create a release branch named according to the major and minor version to be released. This branch is the long lived branch that
   will contain the tagged commit for the release (and possible future patch releases).
   The naming convention is `release/X.Y`. We drop the patch version on release branches so we can make bugfixes there.

2. Bump the version of the package to the version you are about to release by manually editing the `version` field in the `[project]` section of `pyproject.toml`.

3. Update the version identifier in `CITATION.cff` and `meta.yaml`.

4. Update `changelog.md` to ensure the release notes for the version to be published is at the top
   and revisit `README.md` to keep it up to date.

5. Open a PR to merge the release branch into main. This informs the rest of the team how the release
   process is progressing as you polish the release branch. You may need to rebase the release branch onto
   any recent changes to `main` and resolve any conflicts on a regular basis.

6. When you are satisfied that the release branch is ready, tag the latest commit on the release branch with the
   desired version `X.Y.Z` and push the tag upstream. This will kick off the automatic release process.

7. Merge the release branch back into `main` via a PR. Resolve any conflicts normally. This ensures that all changes
   in the release are incorporated into `main` and subsequent version releases.

### Automatic Release Process

We use GitHub Actions for automatic release process that responds to pushes of git tags. When a tag matching
a semantic version (`[0-9]+.[0-9]+.[0-9]+*` or `test-release/[0-9]+.[0-9]+.[0-9]+*`) is pushed, the release workflow
runs as follows:

1. Build distribution artifacts for PyPI.
2. Push the PyPI distribution artifacts to PyPI. Pushes to TestPyPI if tag starts with `test-release`.
3. Build and push the Anaconda distribution to the `lasp` Anaconda channel.
   Pushes with a `test-release` label if tag starts with `test-release`, otherwise labels as `main`.
4. Create a GitHub Release that includes auto-generated release notes and the source code.

#### Official Releases

Official releases are published to the public PyPI (even if they are release candidates like `1.2.3rc1`). This differs
from test releases, which are only published to TestPyPI and are not published to GitHub at all.
If the semantic version has any suffixes (e.g. `rc1`), the release will be marked as
a prerelease in GitHub and PyPI.

To trigger an official release, push a tag referencing the commit you want to release.

```bash
git checkout release/X.Y
git pull
git tag -a X.Y.Z -m "Version X.Y.Z"
git push origin X.Y.Z
```

#### Test Releases

Test releases are published to TestPyPI only and are not published on GitHub. Test releases are triggered by tags
prefixed with `test-release`.

To publish a test release, prefix the tag with `test-release`. This will prevent any publishing to the public PyPI
and will prevent the artifacts being published on GitHub.

```bash
git checkout release/X.Y
git pull
git tag -a test-release/X.Y.Zrc1 -m "Test Release Candidate X.Y.Zrc1"
git push origin test-release/X.Y.Zrc1
```

#### Prereleases

Unless the pushed tag matches the regex `^[0-9]*\.[0-9]*\.[0-9]*`, the release will be marked as a
prerelease in GitHub. This allows "official" prereleases of suffixed tags.

#### Release Notes Generation

Release notes are generated based on commit messages since the latest non-prerelease Release.
