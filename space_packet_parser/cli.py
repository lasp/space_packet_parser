#!/usr/bin/env python3

"""Dependency-light entry points for the Space Packet Parser CLI."""

import sys
from importlib import import_module

CLI_EXTRA_INSTALL_MESSAGE = (
    "The `spp` CLI requires the `cli` extra. Install it with "
    "`pip install space_packet_parser[cli]`."
)
_CLI_EXPORTS = {"spp", "describe_xtce", "describe_packets", "parse", "validate", "console"}


class MissingCliExtraError(ImportError):
    """Raised when the optional CLI dependencies are unavailable."""


def _load_cli_module():
    """Import the CLI implementation or raise a friendly dependency error."""
    try:
        return import_module("space_packet_parser._cli_impl")
    except ModuleNotFoundError as exc:
        if exc.name and exc.name.split(".", 1)[0] in {"click", "rich"}:
            raise MissingCliExtraError(CLI_EXTRA_INSTALL_MESSAGE) from exc
        raise


def main(args=None, prog_name=None) -> None:
    """Console-script entry point for ``spp``."""
    try:
        _load_cli_module().spp.main(args=args, prog_name=prog_name, standalone_mode=True)
    except MissingCliExtraError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc


def __getattr__(name: str):
    """Lazily expose CLI commands while preserving friendly import failures."""
    if name in _CLI_EXPORTS:
        return getattr(_load_cli_module(), name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    """Return module attributes, including lazily loaded CLI exports."""
    return sorted(set(globals()) | _CLI_EXPORTS)


if __name__ == "__main__":
    main()
