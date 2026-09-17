"""Unit tests for the Space Packet Parser `spp` CLI"""

import builtins
import importlib
import importlib.metadata
import sys

import pytest
from click.testing import CliRunner

from space_packet_parser import _spp_entry, cli, exceptions
from space_packet_parser.generators import ccsds_generator


def _block_cli_dependency_imports(monkeypatch):
    """Make `import click` and `import rich` fail and force `space_packet_parser.cli` to be re-imported."""
    real_import = builtins.__import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "click" or name.startswith("click.") or name == "rich" or name.startswith("rich."):
            raise ModuleNotFoundError(f"No module named '{name}'", name=name)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    # monkeypatch restores the already-imported module after the test
    monkeypatch.delitem(sys.modules, "space_packet_parser.cli", raising=False)


def test_cli():
    runner = CliRunner()
    result = runner.invoke(cli.spp, ["--version"])
    print(result.output)
    assert result.exit_code == 0
    print(result.exit_code)

    # Check that the version output contains the actual package version
    expected_version = importlib.metadata.version("space_packet_parser")
    assert expected_version in result.output


def test_spp_entry_point_version(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["spp", "--version"])

    with pytest.raises(SystemExit) as excinfo:
        _spp_entry.main()

    assert excinfo.value.code == 0
    assert importlib.metadata.version("space_packet_parser") in capsys.readouterr().out


def test_spp_entry_point_subcommand(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["spp", "describe-packets", "--help"])

    with pytest.raises(SystemExit) as excinfo:
        _spp_entry.main()

    assert excinfo.value.code == 0
    assert "Describe the header contents of a packet file" in capsys.readouterr().out


def test_spp_entry_point_invalid_subcommand(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["spp", "not-a-command"])

    with pytest.raises(SystemExit) as excinfo:
        _spp_entry.main()

    assert excinfo.value.code == 2
    captured = capsys.readouterr()
    assert "No such command 'not-a-command'" in f"{captured.out}{captured.err}"


def test_describe_xtce_jpss(jpss_test_data_dir):
    runner = CliRunner()
    print()
    result = runner.invoke(cli.describe_xtce, [f"{jpss_test_data_dir / 'jpss1_geolocation_xtce_v1.xml'}"])
    print(result.output)
    assert result.exit_code == 0

    result = runner.invoke(cli.describe_xtce, [f"{jpss_test_data_dir / 'contrived_inheritance_structure.xml'}"])
    print(result.output)
    assert result.exit_code == 0


def test_describe_xtce_suda(suda_test_data_dir):
    runner = CliRunner()
    print()
    result = runner.invoke(cli.describe_xtce, [f"{suda_test_data_dir / 'suda_combined_science_definition.xml'}"])
    print(result.output)
    assert result.exit_code == 0


def test_describe_xtce_ctim_root_container(ctim_test_data_dir):
    """The CTIM definition has no `CCSDSPacket` container, so the root must be overridden."""
    runner = CliRunner()
    print()
    definition_file = str(ctim_test_data_dir / "ctim_xtce_v1.xml")

    result = runner.invoke(cli.describe_xtce, [definition_file])
    print(result.output)
    assert result.exit_code == 2
    assert "No SequenceContainer named 'CCSDSPacket'" in result.output
    assert "possible roots" in result.output
    assert "CCSDSTelemetryPacket" in result.output

    result = runner.invoke(cli.describe_xtce, [definition_file, "--root-container", "CCSDSTelemetryPacket"])
    print(result.output)
    assert result.exit_code == 0
    assert "APID_1_Packet" in result.output


def test_describe_packets_jpss(jpss_test_data_dir):
    runner = CliRunner()
    print()
    result = runner.invoke(
        cli.describe_packets, [f"{jpss_test_data_dir / 'J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1'}"]
    )
    print(result.output)
    assert result.exit_code == 0


def test_parse_jpss(jpss_test_data_dir):
    runner = CliRunner()
    print()
    packet_file = f"{jpss_test_data_dir / 'J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1'}"
    definition_file = f"{jpss_test_data_dir / 'jpss1_geolocation_xtce_v1.xml'}"
    result = runner.invoke(cli.parse, [packet_file, definition_file])
    print(result.output)
    assert result.exit_code == 0


def test_parse_jpss_out_of_range_packet(jpss_test_data_dir):
    runner = CliRunner()
    print()
    packet_file = jpss_test_data_dir / "J01_G011_LZ_2021-04-09T00-00-00Z_V01.DAT1"
    definition_file = jpss_test_data_dir / "jpss1_geolocation_xtce_v1.xml"

    with packet_file.open("rb") as binary_data:
        packet_count = sum(1 for _ in ccsds_generator(binary_data))

    result = runner.invoke(cli.parse, [str(packet_file), str(definition_file), f"--packet={packet_count}"])
    print(result.output)
    assert result.exit_code == 2
    assert f"Packet index {packet_count} out of range" in result.output

    result = runner.invoke(cli.parse, [str(packet_file), str(definition_file), "--packet=-1"])
    print(result.output)
    assert result.exit_code == 2
    assert "Packet index -1 out of range" in result.output


@pytest.mark.filterwarnings("ignore:Number of bits parsed")
def test_parse_ctim_root_container(ctim_test_data_dir):
    """The CTIM definition has no `CCSDSPacket` container, so the root must be overridden."""
    runner = CliRunner()
    print()
    packet_file = str(ctim_test_data_dir / "ccsds_2021_155_14_39_51")
    definition_file = str(ctim_test_data_dir / "ctim_xtce_v1.xml")

    result = runner.invoke(cli.parse, [packet_file, definition_file, "--packet=0"])
    print(result.output)
    assert result.exit_code == 2
    assert "No SequenceContainer named 'CCSDSPacket'" in result.output
    assert "CCSDSTelemetryPacket" in result.output

    result = runner.invoke(
        cli.parse, [packet_file, definition_file, "--packet=0", "--root-container", "CCSDSTelemetryPacket"]
    )
    print(result.output)
    assert result.exit_code == 0


def test_parse_suda(suda_test_data_dir):
    runner = CliRunner()
    print()
    packet_file = f"{suda_test_data_dir / 'sciData_2022_130_17_41_53.spl'}"
    definition_file = f"{suda_test_data_dir / 'suda_combined_science_definition.xml'}"
    result = runner.invoke(cli.parse, [packet_file, definition_file, "--skip-header-bytes=4"])
    print(result.output)
    assert result.exit_code == 0


def test_log_level():
    # Failed on Python < 3.11 due to bad setting of log level
    runner = CliRunner()
    print()
    result = runner.invoke(cli.spp, ["describe-packets", "--help"])
    print(result.output)
    assert result.exit_code == 0


def test_validate_xtce(test_data_dir, mock_schema_download):
    runner = CliRunner()
    _ = mock_schema_download
    print()

    # Test basic validation
    result = runner.invoke(cli.validate, [f"{test_data_dir / 'test_xtce.xml'}"])
    print(result.output)
    assert result.exit_code == 0


def test_validate_xtce_with_local_schema(test_data_dir):
    """Test with local schema option to avoid network dependency"""
    runner = CliRunner()
    print()

    xml_file = test_data_dir / "test_xtce.xml"
    xsd_file = test_data_dir / "SpaceSystem.xsd"

    # Test with local XSD file
    result = runner.invoke(cli.validate, [str(xml_file), "--local-xsd", str(xsd_file)])
    print(result.output)
    assert result.exit_code == 0


def test_validate_xtce_all_options(test_data_dir):
    """Test with all options explicitly set"""
    runner = CliRunner()
    print()

    xml_file = test_data_dir / "test_xtce.xml"
    xsd_file = test_data_dir / "SpaceSystem.xsd"

    # Test with all options set
    result = runner.invoke(
        cli.validate,
        [str(xml_file), "--level", "all", "--timeout", "60", "--local-xsd", str(xsd_file)],
    )
    print(result.output)
    assert result.exit_code == 0

    # Test schema level only
    result = runner.invoke(
        cli.validate,
        [str(xml_file), "--level", "schema", "--timeout", "30", "--local-xsd", str(xsd_file)],
    )
    print(result.output)
    assert result.exit_code == 0

    # Test structure level only
    result = runner.invoke(cli.validate, [str(xml_file), "--level", "structure"])
    print(result.output)
    assert result.exit_code == 0


def test_validate_xtce_failure(test_data_dir):
    """Test failure case"""
    runner = CliRunner()
    print()

    xml_file = test_data_dir / "test_xtce_no_namespace.xml"
    xsd_file = test_data_dir / "SpaceSystem.xsd"

    # Test with all options set
    result = runner.invoke(
        cli.validate,
        [str(xml_file), "--level", "schema", "--local-xsd", str(xsd_file)],
    )
    print(result.output)
    assert "INVALID_XTCE_NAMESPACE" in result.output
    assert "SCHEMA_VALIDATION_ERROR" in result.output
    assert result.exit_code == 1


def test_cli_import_raises_without_cli_extra(monkeypatch):
    _block_cli_dependency_imports(monkeypatch)

    with pytest.raises(ImportError, match="requires the `cli` extra"):
        importlib.import_module("space_packet_parser.cli")


def test_spp_entry_point_exits_with_hint_without_cli_extra(monkeypatch, capsys):
    _block_cli_dependency_imports(monkeypatch)

    with pytest.raises(SystemExit) as excinfo:
        _spp_entry.main()

    assert excinfo.value.code == 1
    assert "pip install space_packet_parser[cli]" in capsys.readouterr().err


def test_spp_entry_point_propagates_unrelated_import_error(monkeypatch):
    """An ImportError that is not the missing `cli` extra must not be converted into the install hint."""
    real_import = builtins.__import__

    def blocked_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "space_packet_parser.xtce.validation":
            raise ModuleNotFoundError(f"No module named '{name}'", name=name)
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", blocked_import)
    monkeypatch.delitem(sys.modules, "space_packet_parser.cli", raising=False)

    with pytest.raises(ModuleNotFoundError, match="space_packet_parser.xtce.validation") as excinfo:
        _spp_entry.main()

    assert not isinstance(excinfo.value, exceptions.MissingExtraError)
