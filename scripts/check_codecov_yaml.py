"""Validate codecov.yml by posting it to Codecov's validation endpoint."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from urllib import error, request

CODECOV_VALIDATE_URL = "https://codecov.io/validate"
NETWORK_TIMEOUT_SECONDS = 10
REPO_ROOT = Path(__file__).parent.parent


def validate_codecov_yaml(file_path: Path) -> int:
    """Validate a Codecov YAML file against Codecov's endpoint."""
    try:
        request_body = file_path.read_bytes()
    except OSError as exc:
        print(f"Unable to read {file_path}: {exc}", file=sys.stderr)
        return 1

    try:
        with request.urlopen(  # noqa: S310
            CODECOV_VALIDATE_URL,
            data=request_body,
            timeout=NETWORK_TIMEOUT_SECONDS,
        ) as response:
            body = response.read().decode("utf-8", errors="replace").strip()
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        print(f"{file_path} validation failed with HTTP {exc.code}.", file=sys.stderr)
        if body:
            print(body, file=sys.stderr)
        return 1
    except (error.URLError, TimeoutError, OSError) as exc:
        print(f"Unable to reach Codecov validation endpoint: {exc}", file=sys.stderr)
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
