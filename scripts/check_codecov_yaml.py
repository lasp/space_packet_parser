"""Validate codecov.yml by posting it to Codecov's validation endpoint."""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

CODECOV_VALIDATE_URL = "https://codecov.io/validate"
REPO_ROOT = Path(__file__).parent.parent


def validate_codecov_yaml(file_path: Path) -> int:
    """Validate a Codecov YAML file against Codecov's endpoint."""
    request = urllib.request.Request(
        CODECOV_VALIDATE_URL,
        data=file_path.read_bytes(),
        method="POST",
        headers={"Content-Type": "text/yaml"},
    )

    try:
        with urllib.request.urlopen(request) as response:
            body = response.read().decode("utf-8", errors="replace").strip()
            if body:
                print(body)
            print(f"{file_path} is valid.")
            return 0
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace").strip()
        print(f"{file_path} validation failed with HTTP {exc.code}.", file=sys.stderr)
        if body:
            print(body, file=sys.stderr)
        return 1
    except urllib.error.URLError as exc:
        print(f"Unable to reach Codecov validation endpoint: {exc.reason}", file=sys.stderr)
        return 1


def main() -> int:
    """Parse CLI args and validate codecov.yml."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--file",
        type=Path,
        default=REPO_ROOT / "codecov.yml",
        help="Path to the codecov YAML file to validate.",
    )
    args = parser.parse_args()
    return validate_codecov_yaml(args.file)


if __name__ == "__main__":
    raise SystemExit(main())
