# GitHub Copilot Instructions for Space Packet Parser

## Project Overview

Space Packet Parser is a Python library for decoding CCSDS (Consultative Committee for Space Data Systems) telemetry packets according to XTCE (XML Telemetric and Command Exchange) packet structure definitions. The library is based on the UML model of the XTCE specification and aims to support all but the most esoteric elements of the XTCE telemetry packet specification.

### Key Concepts

- **CCSDS**: Space data systems standard for space communications
- **XTCE**: XML-based format for describing telemetry and command data structures
- **Telemetry Packets**: Binary data packets from spacecraft/instruments that need to be parsed and decoded

## Technical Requirements

### Python Version

- **Minimum**: Python 3.9+
- **Tested on**: Python 3.9, 3.10, 3.11, 3.12, 3.13

### Core Dependencies

- `lxml>=4.8.0` - XML parsing for XTCE definitions
- `click>=8.0` - CLI framework
- `rich>=13.0` - Terminal formatting and output
- `xarray` (optional) - Multi-dimensional data arrays
- `numpy` (optional) - Numerical computing

## Development Setup

### Installation

```bash
# Install with development dependencies using pip
pip install ".[test,xarray]"

# For development with uv (creates and manages virtual environment)
uv sync --all-extras
```

### Pre-commit Hooks

The project uses pre-commit hooks for code quality. Install them with:

```bash
pre-commit install
```

The hooks include:

- `ruff` for linting and code formatting
- `prettier` for YAML, JSON, and Markdown formatting
- `codespell` for spell checking
- Security checks (AWS credentials, private keys)
- Metadata validation

## Code Style and Linting

### Ruff Configuration

- **Line length**: 120 characters
- **Formatter**: ruff format (follows Black-compatible style)
- **Linter**: Enabled rules include:
  - E/W (pycodestyle errors and warnings)
  - F (pyflakes)
  - I (isort import sorting)
  - S (flake8-bandit security)
  - PT (flake8-pytest-style)
  - UP (pyupgrade syntax upgrader)

### Running Linters

```bash
# Format code
ruff format

# Check and fix linting issues
ruff check --fix

# Run all pre-commit hooks
pre-commit run --all-files
```

## Testing

### Running Tests

```bash
# Run all tests with coverage
pytest --color=yes --cov --cov-report=xml

# Run specific test module
pytest tests/unit/test_xtce/

# Run with verbose output
pytest -v
```

### Test Structure

- `tests/unit/` - Unit tests for individual components
- `tests/integration/` - Integration tests for end-to-end scenarios
- `tests/benchmark/` - Performance benchmarks
- `conftest.py` - Shared test fixtures and configuration

### Test Conventions

- Use pytest fixtures defined in `conftest.py`
- Test data is stored in `tests/test_data/`
- Use pytest parametrize for testing multiple scenarios
- Security checks (S-prefixed rules) are disabled in test files

## Project Structure

### Main Package: `space_packet_parser/`

- `__init__.py` - Public API exports (`load_xtce`, `ccsds_generator`, etc.)
- `cli.py` - Command-line interface using Click
- `common.py` - Common data structures (SpacePacket, etc.)
- `definitions.py` - Core definitions and base classes
- `exceptions.py` - Custom exception classes
- `packets.py` - Packet parsing and handling logic
- `xtce/` - XTCE parsing and validation
  - `definitions.py` - XTCE packet definitions
  - `validation.py` - XTCE schema validation
- `generators/` - Binary data generators and readers
- `xarr.py` - XArray integration (optional feature)

### Examples

Example usage scripts are in `examples/` directory.

### Documentation

- Built with Sphinx
- Uses MyST Parser for Markdown support
- Hosted on ReadTheDocs: https://space-packet-parser.readthedocs.io
- Source files in `docs/source/`

## CLI Tool

The package provides a command-line tool:

```bash
spp <command> [options]
```

Entry point defined in `space_packet_parser.cli:spp`

## Making Changes

### Before Submitting a PR

1. Ensure all tests pass: `pytest`
2. Run linters: `pre-commit run --all-files`
3. Update tests for new functionality
4. Update `docs/source/changelog.md` with your changes
5. Ensure dependencies in `pyproject.toml` are current

### PR Checklist (from template)

- [ ] Changes are fully implemented without dangling issues or TODO items
- [ ] Deprecated/superseded code is removed or marked with deprecation warning
- [ ] Current dependencies have been properly specified and old dependencies removed
- [ ] New code/functionality has accompanying tests and any old tests have been updated
- [ ] The changelog.md has been updated

## Code Review

- Code changes will be reviewed by @medley56 (see CODEOWNERS)
- Follow the project's Code of Conduct

## CI/CD

### GitHub Actions Workflows

- `tests.yml` - Runs tests on Windows, Ubuntu, and macOS across Python 3.9-3.13
- `test_examples.yml` - Validates example scripts
- `release.yml` - Handles package releases

### Coverage

- Code coverage reports are uploaded to Codecov
- Target: Maintain high test coverage for critical components

## Common Tasks

### Adding a New Parameter Type

1. Define the parameter type class in `space_packet_parser/xtce/`
2. Add parsing logic to handle the XTCE element
3. Add unit tests in `tests/unit/test_xtce/test_parameters.py`
4. Add integration test with a real XTCE file if applicable
5. Update documentation

### Adding a New CLI Command

1. Add command function to `space_packet_parser/cli.py`
2. Use Click decorators for arguments/options
3. Use Rich for formatted terminal output
4. Add tests in `tests/unit/test_cli/` (if test directory exists)

### Updating XTCE Validation

1. Modify validation logic in `space_packet_parser/xtce/validation.py`
2. Update schema files if needed
3. Add test cases for the validation scenario
4. Ensure backward compatibility with existing XTCE files

## Important Notes

- The library focuses on **telemetry parsing only** (not command generation)
- Binary data parsing is performance-critical - consider efficiency
- XTCE files can be very large - optimize for memory efficiency
- Support for edge cases in XTCE spec is important for mission use
- This is production code used by real space missions (IMAP, CLARREO, Libera, CTIM-FD, MMS)

## Resources

- [XTCE Green Book (Informational Report)](https://public.ccsds.org/Pubs/660x2g2.pdf)
- [XTCE Element Description (Green Book)](https://public.ccsds.org/Pubs/660x1g2.pdf)
- [XTCE Blue Book (Recommended Standard)](https://public.ccsds.org/Pubs/660x0b2.pdf)
- [Project Documentation](https://space-packet-parser.readthedocs.io)
- [PyHC (Python in Heliophysics Community)](https://heliopython.org)
