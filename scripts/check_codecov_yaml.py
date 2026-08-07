"""Validate codecov.yml by posting it to Codecov's validation endpoint."""

from __future__ import annotations

import argparse
import http.client
import sys
from pathlib import Path

CODECOV_VALIDATE_HOST = "codecov.io"
CODECOV_VALIDATE_PATH = "/validate"
REPO_ROOT = Path(__file__).parent.parent


def validate_codecov_yaml(file_path: Path) -> int:
    """Validate a Codecov YAML file against Codecov's endpoint."""
    try:
        conn = http.client.HTTPSConnection(CODECOV_VALIDATE_HOST)
        conn.request(
            method="POST",
            url=CODECOV_VALIDATE_PATH,
            body=file_path.read_bytes(),
            headers={"Content-Type": "text/yaml"},
        )
        response = conn.getresponse()
        body = response.read().decode("utf-8", errors="replace").strip()
    except OSError as exc:
        print(f"Unable to reach Codecov validation endpoint: {exc}", file=sys.stderr)
        return 1
    finally:
        if "conn" in locals():
            conn.close()

    if response.status >= 400:
        print(f"{file_path} validation failed with HTTP {response.status}.", file=sys.stderr)
        if body:
            print(body, file=sys.stderr)
        return 1

    if body:
        print(body)
    print(f"{file_path} is valid.")
    return 0


def main() -> int:
    """Parse CLI args and validate codecov.yml."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file",
        type=Path,
        default=REPO_ROOT / "codecov.yml",
        help="Path to the codecov YAML file to validate.",
    )
    parser.add_argument(
        "files",
        nargs="*",
        type=Path,
        help="Optional file paths provided by pre-commit.",
    )
    args = parser.parse_args()
    files_to_validate = args.files or [args.file]
    exit_code = 0
    for file_path in files_to_validate:
        if validate_codecov_yaml(file_path) != 0:
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
