# Parsing Packets to Xarray Datasets

For analysis and visualization workflows, Space Packet Parser can parse packets directly into
Xarray Datasets using the `create_dataset` function. This is particularly useful when working with
timeseries telemetry data. Note that this requires installing the optional `xarray` dependencies:

```bash
pip install space_packet_parser[xarray]
```

The `create_dataset` function returns a dictionary of Datasets keyed by APID, where each Dataset
contains all parameters from packets with that APID:

```python
from pathlib import Path
import space_packet_parser as spp
from space_packet_parser.xarr import create_dataset

packet_file = Path("my_packets.pkts")
xtce_definition_file = Path("my_xtce_document.xml")

# Parse packets directly to Xarray Datasets (one per APID)
datasets = create_dataset(
    packet_files=[packet_file],
    xtce_packet_definition=xtce_definition_file
)

# Access dataset for a specific APID
apid_1_data = datasets[1]
print(apid_1_data)

# Work with the data
print(apid_1_data["MY_PARAMETER"].values)
```

You can filter packets by APID or other criteria by passing a `packet_filter` function. This is
useful when working with multiplexed packet streams:

```python
# Filter to only parse packets with APID 41
datasets = create_dataset(
    packet_files=[packet_file],
    xtce_packet_definition=xtce_definition_file,
    packet_filter=lambda pkt: pkt.apid == 41
)
```

For a complete, runnable script, see the
[Xarray dataset example](https://github.com/lasp/space_packet_parser/blob/main/examples/parsing_to_xarray_dataset.py).

**Limitations**: The `create_dataset` function only supports packet definitions with consistent
field structure across all packets with the same APID. It cannot handle polymorphic packets where
the structure changes based on previously parsed values. For such cases, use the low-level parsing
API by calling the `parse_bytes()` method directly.
