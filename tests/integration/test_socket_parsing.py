"""Mock socket streaming and listener that decodes on the fly"""

import random
import socket
import time
from contextlib import closing
from threading import Thread

import pytest

from space_packet_parser import generators
from space_packet_parser.xtce.definitions import XtcePacketDefinition


def send_data(sender: socket.socket, file: str):
    """Send data from a file as bytes via a socket with random chunk sizes and random waits between sending chunks

    Parameters
    ----------
    sender : socket.socket
        Socket over which to send the data.
    file : str
        File to send as bytes over a socket connection
    """
    # Read binary file
    with open(file, "rb") as fh:
        stream = fh.read()
        pos = 0
        while pos < len(stream):
            time.sleep(random.random() * 0.1)  # Random sleep up to 1s
            # Send binary data to socket in random chunk sizes
            min_n_bytes = 4096
            max_n_bytes = 4096 * 2
            random_n_bytes = int(random.random()) * (max_n_bytes - min_n_bytes)
            n_bytes_to_send = 8 * (min_n_bytes + random_n_bytes)
            if pos + n_bytes_to_send > len(stream):
                n_bytes_to_send = len(stream) - pos
            chunk_to_send = stream[pos : pos + n_bytes_to_send]
            sender.send(chunk_to_send)
            pos += n_bytes_to_send
        print("\nFinished sending data.")


def test_parsing_from_socket(jpss_test_data_dir):
    # Create packet def
    xdef = XtcePacketDefinition.from_xtce(jpss_test_data_dir / "jpss1_geolocation_xtce_v1.xml")
    # Create socket
    sender, receiver = socket.socketpair()
    receiver.settimeout(3)
    with closing(sender), closing(receiver):
        file = jpss_test_data_dir / "J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1"
        t = Thread(
            target=send_data,
            args=(
                sender,
                file,
            ),
        )
        t.start()

        ccsds_generator = generators.ccsds_generator(receiver, buffer_read_size_bytes=4096)
        packets = []
        with pytest.raises(socket.timeout):  # noqa PT012
            for packet_bytes in ccsds_generator:
                p = xdef.parse_bytes(packet_bytes)
                packets.append(p)
        t.join()

    assert len(packets) == 7200
