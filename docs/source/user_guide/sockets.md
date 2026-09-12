# Parsing from a Socket

The input data object to a packet generator (e.g. `ccsds_generator`) need only be a binary
file-like object from which bytes can be read. This means packet parsing is not limited to reading
from files — you can parse packet data streaming through a socket, too. In an effort to support
development of quicklook-type tools, we provide an example of parsing data streaming through a
socket in
[`parsing_and_plotting_idex_waveforms_from_socket.py`](https://github.com/lasp/space_packet_parser/blob/main/examples/parsing_and_plotting_idex_waveforms_from_socket.py).

The example mocks the behavior of an instrument sending packet data asynchronously through a
socket in chunks of inconsistent size. The packet parser reads bytes from the receiver side of the
socket and reads data repeatedly until there is sufficient data for a full packet. Once it has a
full packet (as determined by the packet length in the CCSDS header), it yields a parsed packet.

You'll notice that the example ends with a timeout error. This timeout can be controlled when
creating the socket connection with `receiver.settimeout(timeout_seconds)`.
