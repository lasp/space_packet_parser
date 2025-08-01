from space_packet_parser import load_xtce
from space_packet_parser.common import fixed_length_generator


def test_fixed_length_generator():
    # Create a bytes object with 3 packets of length 4
    data = b'ABCD' + b'EFGH' + b'IJKL'
    binary_packets = list(fixed_length_generator(data, packet_length_bytes=4))
    assert binary_packets == [b'ABCD', b'EFGH', b'IJKL']


def test_fixed_length_generator_with_xtce(test_data_dir):
    d = load_xtce(test_data_dir / "test_xtce_4byte.xml")
    d.root_container_name = "PKT_CONTAINER"
    packet_length_bytes = 4

    # Two 0 ints and a max int
    empty_binary_data = b'\x00'*packet_length_bytes*2 + b'\xFF'*packet_length_bytes
    generator = fixed_length_generator(
        binary_data=empty_binary_data,
        packet_length_bytes=packet_length_bytes
    )
    packets = [d.parse_bytes(binary_data) for binary_data in generator]
    assert len(packets) == 3
    assert packets[0] == {'PKT_VALUE': 0}
    assert packets[-1] == {'PKT_VALUE': 2**32 - 1}
