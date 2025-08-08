"""Script for CI that verifies metadata matches between pyproject.toml, meta.yaml, and CITATION.cff"""

from pathlib import Path

try:
    import tomllib  # >=3.11
except ImportError:
    import tomli as tomllib  # <3.11
import yaml

REPO_ROOT = Path(__file__).parent.parent


def parse_pyproject_toml(file_path: Path) -> dict:
    """Parse pyproject.toml and return the full data."""
    with file_path.open("rb") as f:
        return tomllib.load(f)


def parse_citation_cff(file_path: Path) -> dict:
    """Parse CITATION.cff and return the full data."""
    with file_path.open() as f:
        return yaml.safe_load(f)


def parse_meta_yaml(file_path: Path) -> dict:
    """Parse meta.yaml and return the full data."""
    with file_path.open() as f:
        return yaml.safe_load(f)


def verify_name(pyproject_toml, citation_cff, meta_yaml):
    """Verify that names match"""
    pyproject_name = pyproject_toml["project"]["name"]
    citation_name = citation_cff["title"]
    meta_name = meta_yaml["package"]["name"]
    if not (pyproject_name == citation_name == meta_name):
        print(f"pyproject.toml: {pyproject_name}")
        print(f"CITATION.cff: {citation_name}")
        print(f"meta.yaml: {meta_name}")
        raise ValueError("Names do not match")
    print("Names match")


def verify_description(pyproject_toml, citation_cff, meta_yaml):
    """Verify that descriptions match"""
    pyproject_description = pyproject_toml["project"]["description"]
    citation_description = citation_cff["description"]
    meta_description = meta_yaml["about"]["description"]
    if not (pyproject_description == citation_description == meta_description):
        print(f"pyproject.toml: {pyproject_description}")
        print(f"CITATION.cff: {citation_description}")
        print(f"meta.yaml: {meta_description}")
        raise ValueError("Descriptions do not match")
    print("Descriptions match")


def verify_version(pyproject_toml, citation_cff, meta_yaml):
    """Verify that version strings match"""
    pyproject_version = pyproject_toml["project"]["version"]
    citation_version = citation_cff["version"]
    meta_version = meta_yaml["package"]["version"]
    if not (pyproject_version == citation_version == meta_version):
        print(f"pyproject.toml: {pyproject_version}")
        print(f"CITATION.cff: {citation_version}")
        print(f"meta.yaml: {meta_version}")
        raise ValueError("Versions do not match")
    print("Versions match")


def verify_license(pyproject_toml, citation_cff, meta_yaml):
    """Verify that licenses match"""
    pyproject_license = pyproject_toml["project"]["license"]["text"]
    citation_license = citation_cff["license"]
    meta_license = meta_yaml["about"]["license"]
    if not (pyproject_license == citation_license == meta_license):
        print(f"pyproject.toml: {pyproject_license}")
        print(f"CITATION.cff: {citation_license}")
        print(f"meta.yaml: {meta_license}")
        raise ValueError("Licenses do not match")
    print("Licenses match")


def verify_authors(pyproject_toml, citation_cff, meta_yaml):
    """Verify that authors match"""
    pyproject_authors = {(a["name"], a["email"]) for a in pyproject_toml["project"]["authors"]}
    citation_authors = {(a["name"], a["email"]) for a in citation_cff["authors"]}
    if not pyproject_authors == citation_authors:
        print(f"pyproject.toml: {pyproject_authors}")
        print(f"CITATION.cff: {citation_authors}")
        raise ValueError("Authors do not match")
    print("Authors match")


def verify_maintainers(pyproject_toml, citation_cff, meta_yaml):
    """Verify that maintainers match"""
    pyproject_maintainers = {(a["name"], a["email"]) for a in pyproject_toml["project"]["maintainers"]}
    citation_maintainers = {(a["name"], a["email"]) for a in citation_cff["maintainers"]}
    if not pyproject_maintainers == citation_maintainers:
        print(f"pyproject.toml: {pyproject_maintainers}")
        print(f"CITATION.cff: {citation_maintainers}")
        raise ValueError("Maintainers do not match")
    print("Maintainers match")


def verify_dependencies(pyproject_toml, citation_cff, meta_yaml):
    """Verify that dependencies match"""
    pyproject_dependencies = set(pyproject_toml["project"]["dependencies"])
    pyproject_dependencies.add(f"python{pyproject_toml['project']['requires-python']}")
    # Conda doesn't have the concept of extras, so we list the xarray extras as explicit deps for conda package
    pyproject_dependencies = pyproject_dependencies.union(
        set(pyproject_toml["project"]["optional-dependencies"]["xarray"])
    )
    meta_dependencies = set(meta_yaml["requirements"]["run"])
    if not pyproject_dependencies == meta_dependencies:
        print(f"pyproject.toml: {pyproject_dependencies}")
        print(f"meta.yaml: {meta_dependencies}")
        raise ValueError("Dependencies do not match")
    print("Dependencies match (does not check extras or test dependencies)")


def main():
    """Ensure metadata consistency across files."""
    print("Checking metadata consistency between pyproject.toml, meta.yaml, and CITATION.cff")
    pyproject_data = parse_pyproject_toml(REPO_ROOT / "pyproject.toml")
    citation_data = parse_citation_cff(REPO_ROOT / "CITATION.cff")
    meta_data = parse_meta_yaml(REPO_ROOT / "meta.yaml")

    verify_name(pyproject_data, citation_data, meta_data)
    verify_description(pyproject_data, citation_data, meta_data)
    verify_authors(pyproject_data, citation_data, meta_data)
    verify_maintainers(pyproject_data, citation_data, meta_data)
    verify_version(pyproject_data, citation_data, meta_data)
    verify_license(pyproject_data, citation_data, meta_data)
    verify_dependencies(pyproject_data, citation_data, meta_data)

    print("Metadata is consistent across all files.")


if __name__ == "__main__":
    main()
