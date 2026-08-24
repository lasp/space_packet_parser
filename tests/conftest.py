"""Test fixtures"""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from lxml import etree
from lxml.builder import ElementMaker

from space_packet_parser import common
from space_packet_parser.xtce import STANDARD_XTCE_NS_PREFIX, STANDARD_XTCE_NSMAP, XTCE_1_2_XMLNS


@pytest.fixture(scope="session")
def elmaker():
    """ElementMaker for testing XML element creation"""
    return ElementMaker(namespace=XTCE_1_2_XMLNS, nsmap=STANDARD_XTCE_NSMAP)


@pytest.fixture
def xtce_parser():
    """Parser for testing that knows about the standard testing namespace we use"""
    el = common.NamespaceAwareElement
    el.set_nsmap(STANDARD_XTCE_NSMAP)
    el.set_ns_prefix(STANDARD_XTCE_NS_PREFIX)
    xtce_element_lookup = etree.ElementDefaultClassLookup(element=el)
    xtce_parser = etree.XMLParser()
    xtce_parser.set_element_class_lookup(xtce_element_lookup)
    return xtce_parser


@pytest.fixture
def test_data_dir():
    """Returns the test data directory"""
    return Path(sys.modules[__name__.split(".")[0]].__file__).parent / "test_data"


@pytest.fixture
def ctim_test_data_dir(test_data_dir):
    """CTIM test data directory"""
    return test_data_dir / "ctim"


@pytest.fixture
def jpss_test_data_dir(test_data_dir):
    """JPSS test data directory"""
    return test_data_dir / "jpss"


@pytest.fixture
def clarreo_test_data_dir(test_data_dir):
    """CLARREO test data directory"""
    return test_data_dir / "clarreo"


@pytest.fixture
def suda_test_data_dir(test_data_dir):
    """SUDA test data directory"""
    return test_data_dir / "suda"


@pytest.fixture
def idex_test_data_dir(test_data_dir):
    """IDEX test data directory"""
    return test_data_dir / "idex"


@pytest.fixture
def mock_schema_download(test_data_dir):
    """Mock urlopen to return local XSD content instead of downloading from the network.

    Shared by unit and integration tests. Note: documents that reference the standard OMG
    schema URL are now served from the bundled schema without any network call, so this mock
    is only exercised for non-bundled URLs.
    """
    local_xsd_path = test_data_dir / "SpaceSystem.xsd"

    def mock_urlopen(url, timeout=None):
        """Mock urlopen that returns local XSD content."""

        class MockResponse:
            def __init__(self, content):
                self.content = content
                self.headers = {}

            def read(self, *args):
                return self.content

            def __enter__(self):
                return self

            def __exit__(self, *args):
                pass

        # Read the local XSD file
        with local_xsd_path.open("rb") as f:
            content = f.read()

        return MockResponse(content)

    with patch("space_packet_parser.xtce.validation.urlopen", side_effect=mock_urlopen):
        yield
