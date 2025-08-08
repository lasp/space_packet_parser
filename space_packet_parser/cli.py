#!/usr/bin/env python3

"""Command line interface to the Space Packet Parsing library.

This module serves as a command line utility to inspect and process packet data.

Use
---
    spp <command> [<args>]
    spp --help
    spp --describe <packet_file>
"""

import logging
from pathlib import Path
from typing import Optional

import click
from rich import pretty
from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree

from space_packet_parser import ccsds
from space_packet_parser.ccsds import ccsds_generator
from space_packet_parser.xtce.definitions import DEFAULT_ROOT_CONTAINER, XtcePacketDefinition

# Initialize a console instance for rich output
console = Console()

# Maximum number of rows to display
MAX_ROWS = 10
HEAD_ROWS = 5
# Standard names for header field values when inspecting packets without an XTCE definition
DISPLAY_HEADER_FIELDS = ("VER", "TYPE", "SHFLG", "APID", "SEQFLG", "SEQCNT", "PKTLEN")


@click.group(context_settings={"show_default": True})
@click.version_option(message="Space Packet Parser CLI (%(prog)s) v%(version)s")
@click.option("-v", "--verbose", is_flag=True, help="Enable verbose output (DEBUG logging)")
@click.option("-q", "--quiet", is_flag=True, help="Disable logging output entirely")
@click.option("--log-level", default="INFO", help="Log level, e.g. WARNING, INFO, DEBUG. Ignored if -q or -v is set.")
def spp(verbose, quiet, log_level):
    """Command line utility for working with CCSDS packets."""
    # Set logging level
    # Map log level names to numeric values for Python versions < 3.11
    # TODO: Change this to logging.getLevelNamesMapping() when we support only 3.11+
    level_mapping = {
        "CRITICAL": logging.CRITICAL,
        "ERROR": logging.ERROR,
        "WARNING": logging.WARNING,
        "INFO": logging.INFO,
        "DEBUG": logging.DEBUG,
        "NOTSET": logging.NOTSET,
    }
    loglevel = level_mapping.get(log_level.upper(), logging.INFO)
    if verbose:
        loglevel = logging.DEBUG
    elif quiet:
        loglevel = logging.CRITICAL

    # Configure logging with RichHandler for colorized output
    logging.basicConfig(
        level=loglevel,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)],
    )
    logging.getLogger("rich").setLevel(loglevel)


@spp.command()
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.option("--sequence-containers", is_flag=True, help="Display sequence containers")
@click.option("--parameters", is_flag=True, help="Display parameters")
@click.option("--parameter-types", is_flag=True, help="Display parameter types")
@click.option(
    "--root-container",
    default=DEFAULT_ROOT_CONTAINER,
    help=f"Name of root SequenceContainer element. Default is {DEFAULT_ROOT_CONTAINER}.",
)
def describe_xtce(
    file_path: Path, sequence_containers: bool, parameters: bool, parameter_types: bool, root_container: str
) -> None:
    """Describe the contents and structure of an XTCE packet definition file."""
    logging.debug(f"Describing XTCE file: {file_path}")
    definition = XtcePacketDefinition.from_xtce(file_path, root_container_name=root_container)
    tree = Tree(definition.root_container_name)

    # Recursively add nodes based on the inheritors of each container
    def add_nodes(tree_node, parent_key):
        children = definition.containers[parent_key].inheritors
        for child_key in children:
            # Create a new child node (name + comparisons used to distinguish between containers)
            child_node = tree_node.add(f"{child_key} {definition.containers[child_key].restriction_criteria}")
            # Recursively add any children of this child
            add_nodes(child_node, child_key)

    add_nodes(tree, definition.root_container_name)

    console.print(Panel(tree, title="XTCE Container Layout", border_style="cyan", expand=False))
    if sequence_containers:
        console.print(
            Panel(
                pretty.Pretty(definition.containers),
                title=f"Sequence Containers ({len(definition.containers)})",
                border_style="blue",
                expand=False,
            )
        )
    if parameters:
        console.print(
            Panel(
                pretty.Pretty(definition.parameters),
                title=f"Parameters ({len(definition.parameters)})",
                border_style="green",
                expand=False,
            )
        )
    if parameter_types:
        console.print(
            Panel(
                pretty.Pretty(definition.parameter_types),
                title=f"Parameter Types ({len(definition.parameter_types)})",
                border_style="magenta",
                expand=False,
            )
        )


@spp.command()
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
# TODO: Allow multiple file paths, ordered
# TODO: Allow filtering by header values
def describe_packets(file_path: Path) -> None:
    """Describe the header contents of a packet file, no packet definition required."""
    logging.debug(f"Describing packet file: {file_path}")
    with open(file_path, "rb") as f:
        packets = list(ccsds_generator(f))

    npackets = len(packets)
    if npackets == 0:
        console.print(f"No packets found in {file_path}")
        return

    # Create table for packet data display
    table = Table(
        title=f"[bold magenta]{file_path}: {npackets} packets[/bold magenta]",
        show_header=True,
        header_style="bold magenta",
    )

    # Add columns for header fields only
    for key in DISPLAY_HEADER_FIELDS:
        table.add_column(key)

    # Determine rows to display (head and tail with ellipsis if necessary)
    if npackets > MAX_ROWS:
        packets_to_show = packets[:HEAD_ROWS] + packets[-HEAD_ROWS:]
    else:
        packets_to_show = packets

    # Add rows to the table
    for packet in packets_to_show[:HEAD_ROWS]:
        table.add_row(*[str(value) for value in packet.header_values])

    # Add ellipsis if there are more packets
    if npackets > MAX_ROWS:
        table.add_row(*["..." for _ in packets[0].header_values])

    for packet in packets_to_show[-HEAD_ROWS:]:
        table.add_row(*[str(value) for value in packet.header_values])

    # Print the table
    console.print(table, overflow="ellipsis")


@spp.command()
@click.argument("packet_file", type=click.Path(exists=True, path_type=Path))
@click.argument("definition_file", type=click.Path(exists=True, path_type=Path))
@click.option("--packet", type=int, default=None, help="Display the packet at the given index (0-indexed)")
@click.option("--max-items", type=int, default=20, help="Maximum number of items to display")
@click.option("--max-string", type=int, default=40, help="Maximum length of string data")
@click.option("--skip-header-bytes", type=int, default=0, help="Number of bytes to skip before each packet")
def parse(
    packet_file: Path,
    definition_file: Path,
    packet: Optional[int],
    max_items: int,
    max_string: int,
    skip_header_bytes: int,
) -> None:
    """Parse a packet file using the provided XTCE definition."""
    logging.debug(f"Parsing packet file: {packet_file}")
    logging.debug(f"Using packet definition file: {definition_file}")
    packet_definition = XtcePacketDefinition.from_xtce(definition_file)
    with open(packet_file, "rb") as f:
        ccsds_generator = ccsds.ccsds_generator(f, skip_header_bytes=skip_header_bytes)
        packets = [packet_definition.parse_bytes(binary_data) for binary_data in ccsds_generator]

    if packet is not None:
        if packet > len(packets):
            console.print(f"Packet index {packet} out of range with only {len(packets)} packets in the file")
            return
        packets = packets[packet]
    # Limit the number of packets and variables printed
    # also limit the length of strings (binary data can be long)
    pretty.pprint(packets, indent_guides=False, max_length=max_items, max_string=max_string)


@spp.command()
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--level",
    default="schema",
    type=click.Choice(["schema", "structure", "all"]),
    help="Validation level to perform. Default is 'schema'.",
)
@click.option("--schema-url", help="Explicit schema URL to use for validation")
@click.option(
    "--local-schema",
    type=click.Path(exists=True, path_type=Path),
    help="Local XSD schema file to use instead of downloading",
)
@click.option("--timeout", default=30, help="Timeout in seconds for schema downloads")
@click.option("--quiet", is_flag=True, help="Only show errors and warnings")
@click.option("--verbose", is_flag=True, help="Show all validation details including info messages")
def validate_xtce(
    file_path: Path,
    level: str,
    schema_url: Optional[str],
    local_schema: Optional[Path],
    timeout: int,
    quiet: bool,
    verbose: bool,
) -> None:
    """Validate an XTCE packet definition file.

    This command validates XTCE documents at different levels:

    - schema: Validate against XSD schema (fastest)
    - structure: Validate XTCE structure and references
    - all: Perform all validation levels

    Examples:

        spp validate-xtce my_xtce.xml

        spp validate-xtce my_xtce.xml --level all --verbose

        spp validate-xtce my_xtce.xml --local-schema xtce_schema.xsd
    """
    logging.debug(f"Validating XTCE file: {file_path} at level: {level}")

    try:
        # Perform validation using the validation module directly
        from space_packet_parser.xtce.validation import validate_document

        result = validate_document(
            file_path,
            level=level,
            schema_url=schema_url,
            local_schema_path=str(local_schema) if local_schema else None,
            timeout=timeout,
        )

        # Determine what to display based on quiet/verbose flags
        show_errors = True
        show_warnings = not quiet
        show_info = verbose and not quiet

        # Create output
        if result.valid:
            status_color = "green"
            status_text = "✓ VALID"
        else:
            status_color = "red"
            status_text = "✗ INVALID"

        # Display header
        header_text = f"{status_text} - {level.title()} Validation"
        if result.validation_time_ms:
            header_text += f" ({result.validation_time_ms:.1f}ms)"

        console.print(Panel(header_text, style=status_color))

        # Display validation details
        if result.schema_location:
            console.print(f"Schema: {result.schema_location}")
        if result.schema_version:
            console.print(f"Version: {result.schema_version}")
        console.print()

        # Display errors
        if show_errors and result.errors:
            console.print(f"[red]Errors ({len(result.errors)}):[/red]")
            for error in result.errors:
                location = ""
                if error.line_number:
                    location = f" (line {error.line_number})"
                elif error.xpath_location:
                    location = f" ({error.xpath_location})"
                console.print(f"  • {error.message}{location}", style="red")
            console.print()

        # Display warnings
        if show_warnings and result.warnings:
            console.print(f"[yellow]Warnings ({len(result.warnings)}):[/yellow]")
            for warning in result.warnings:
                location = ""
                if warning.line_number:
                    location = f" (line {warning.line_number})"
                elif warning.xpath_location:
                    location = f" ({warning.xpath_location})"
                console.print(f"  • {warning.message}{location}", style="yellow")
            console.print()

        # Display info messages
        if show_info and result.info_messages:
            console.print(f"[blue]Info ({len(result.info_messages)}):[/blue]")
            for info in result.info_messages:
                console.print(f"  • {info.message}", style="blue")
            console.print()

        # Summary
        if not quiet:
            summary_parts = []
            if result.errors:
                summary_parts.append(f"{len(result.errors)} error(s)")
            if result.warnings:
                summary_parts.append(f"{len(result.warnings)} warning(s)")
            if result.info_messages and verbose:
                summary_parts.append(f"{len(result.info_messages)} info message(s)")

            if summary_parts:
                console.print(f"Summary: {', '.join(summary_parts)}")
            else:
                console.print("Summary: No issues found")

        # Exit with appropriate code
        if result.errors:
            exit(1)  # Errors found
        else:
            exit(0)  # Valid or warnings only

    except Exception as e:
        console.print(f"[red]Validation failed with exception: {e}[/red]")
        logging.exception("Validation command failed")
        exit(2)  # Command failed
