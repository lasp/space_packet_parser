"""Console-script entry point for ``spp``.

PEP 621 metadata cannot condition a console script on an extra, so ``spp`` is installed even without
the ``cli`` extra. This module imports nothing from ``click`` or ``rich`` itself, so a bare install gets
an install hint and a non-zero exit instead of a traceback.
"""

import sys


def main() -> None:
    """Run the ``spp`` command line interface."""
    try:
        from space_packet_parser.cli import spp
    except ImportError as exc:
        print(exc, file=sys.stderr)
        raise SystemExit(1) from exc
    spp()
