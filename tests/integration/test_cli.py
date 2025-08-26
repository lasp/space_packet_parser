"""Unit tests for the Space Packet Parser `spp` CLI"""

import importlib.metadata

from click.testing import CliRunner

from space_packet_parser import cli


def test_cli():
    runner = CliRunner()
    result = runner.invoke(cli.spp, ["--version"])
    print(result.output)
    assert result.exit_code == 0
    print(result.exit_code)

    # Check that the version output contains the actual package version
    expected_version = importlib.metadata.version("space_packet_parser")
    assert expected_version in result.output


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


def test_validate_xtce(test_data_dir):
    runner = CliRunner()
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
