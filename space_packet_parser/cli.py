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
from typing import Union

import click
from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler
from rich.panel import Panel
from rich.tree import Tree
from rich import pretty

from space_packet_parser.packets import packet_generator
from space_packet_parser.definitions import XtcePacketDefinition

# Initialize a console instance for rich output
console = Console()

# Maximum number of rows to display
MAX_ROWS = 10
HEAD_ROWS = 5


@click.group(context_settings={'show_default': True})
@click.version_option()
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug output"
)
@click.option(
    "-v", "--verbose", is_flag=True, help="Enable verbose output"
)
def cli(debug, verbose):
    """Command line utility for working with CCSDS packets."""
    # Set logging level
    loglevel = logging.WARNING
    if debug:
        loglevel = logging.DEBUG
    elif verbose:
        loglevel = logging.INFO

    # Configure logging with RichHandler for colorized output
    logging.basicConfig(
        level=loglevel,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(console=console, rich_tracebacks=True)]
    )
    logging.getLogger("rich").setLevel(loglevel)


@cli.command()
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
@click.option("--sequence-containers", is_flag=True, help="Display sequence containers")
@click.option("--parameters", is_flag=True, help="Display parameters")
@click.option("--parameter-types", is_flag=True, help="Display parameter types")
def describe_xtce(file_path: Path, sequence_containers: bool, parameters: bool, parameter_types: bool) -> None:
    """Describe the contents of an XTCE file."""
    # pylint: disable=protected-access
    logging.debug(f"Describing XTCE file: {file_path}")
    definition = XtcePacketDefinition(file_path)
    tree = Tree(definition.root_container_name)

    # Recursively add nodes based on the inheritors of each container
    def add_nodes(tree_node, parent_key):
        children = definition._sequence_container_cache[parent_key].inheritors
        for child_key in children:
            # Create a new child node (name + comparisons used to distinguish between containers)
            child_node = tree_node.add(
                f"{child_key} {definition._sequence_container_cache[child_key].restriction_criteria}")
            # Recursively add any children of this child
            add_nodes(child_node, child_key)
    add_nodes(tree, definition.root_container_name)

    console.print(Panel(tree, title="XTCE Container Layout", border_style="cyan", expand=False))
    if sequence_containers:
        console.print(Panel(pretty.Pretty(definition._sequence_container_cache),
                            title=f"Sequence Containers ({len(definition._sequence_container_cache)})",
                            border_style="blue", expand=False))
    if parameters:
        console.print(Panel(pretty.Pretty(definition._parameter_cache),
                            title=f"Parameters ({len(definition._parameter_cache)})",
                            border_style="green", expand=False))
    if parameter_types:
        console.print(Panel(pretty.Pretty(definition._parameter_type_cache),
                            title=f"Parameter Types ({len(definition._parameter_type_cache)})",
                            border_style="magenta", expand=False))


@cli.command()
@click.argument("file_path", type=click.Path(exists=True, path_type=Path))
def describe_packets(file_path: Path) -> None:
    """Describe the contents of a packet file."""
    logging.debug(f"Describing packet file: {file_path}")
    with open(file_path, "rb") as f:
        packets = list(packet_generator(f))

    npackets = len(packets)
    if npackets == 0:
        console.print(f"No packets found in {file_path}")
        return

    # Create table for packet data display
    table = Table(title=f"[bold magenta]{file_path}: {npackets} packets[/bold magenta]",
                  show_header=True,
                  header_style="bold magenta")

    # Add columns dynamically based on the first packet's keys
    for key in packets[0]:
        table.add_column(key)

    # Determine rows to display (head and tail with ellipsis if necessary)
    if npackets > MAX_ROWS:
        packets_to_show = packets[:HEAD_ROWS] + packets[-HEAD_ROWS:]
    else:
        packets_to_show = packets

    # Add rows to the table
    for packet in packets_to_show[:HEAD_ROWS]:
        table.add_row(*[str(value) for value in packet.values()])

    # Add ellipsis if there are more packets
    if npackets > MAX_ROWS:
        table.add_row(*["..." for _ in packets[0]])

    for packet in packets_to_show[-HEAD_ROWS:]:
        table.add_row(*[str(value) for value in packet.values()])

    # Print the table
    console.print(table, overflow="ellipsis")


@cli.command()
@click.argument("packet_file", type=click.Path(exists=True, path_type=Path))
@click.argument("definition_file", type=click.Path(exists=True, path_type=Path))
@click.option("--packet", type=int, default=None, help="Display the packet at the given index (0-indexed)")
@click.option("--max-items", type=int, default=20, help="Maximum number of items to display")
@click.option("--max-string", type=int, default=40, help="Maximum length of string data")
def parse(packet_file: Path, definition_file: Path, packet: Union[int, None], max_items: int, max_string: int) -> None:
    """Parse a packet file using the provided XTCE definition."""
    logging.debug(f"Parsing packet file: {packet_file}")
    logging.debug(f"Using packet definition file: {definition_file}")

    with open(packet_file, "rb") as f:
        packets = list(packet_generator(f, definition=XtcePacketDefinition(definition_file)))

    if packet is not None:
        if packet > len(packets):
            console.print(f"Packet index {packet} out of range with only {len(packets)} packets in the file")
            return
        packets = packets[packet]
    # Limit the number of packets and variables printed
    # also limit the length of strings (binary data can be long)
    pretty.pprint(packets, indent_guides=False, max_length=max_items, max_string=max_string)
