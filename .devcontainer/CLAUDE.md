# Space Packet Parser Development Context

## Project Overview
Space Packet Parser is a Python library for decoding CCSDS telemetry packets according to XTCE packet structure definitions. It's used by multiple space missions for processing and analyzing spacecraft telemetry data.

## Key Technologies
- **Python 3.9+** - Core language
- **Poetry** - Dependency management and packaging
- **XTCE/CCSDS Standards** - Packet format specifications
- **lxml** - XML parsing for XTCE definitions
- **Click** - CLI interface
- **Rich** - Terminal output formatting
- **XArray** - Optional data array support
- **pytest** - Testing framework
- **Ruff** - Linting and formatting

## Architecture
- `space_packet_parser/` - Main package
  - `packets.py` - Core packet parsing logic
  - `xtce/` - XTCE standard implementation
  - `cli.py` - Command-line interface
  - `xarr.py` - XArray integration
- `tests/` - Comprehensive test suite with unit and integration tests
- `examples/` - Usage examples and demonstrations
- `docs/` - Sphinx documentation

## Development Guidelines

### Code Quality
- Follow the existing code style and patterns
- Use Ruff for linting (configured in pyproject.toml)
- Maintain high test coverage
- Write clear docstrings for public APIs
- Avoid inline imports unless absolutely necessary

### Testing
- Run tests with: `pytest`
- Include benchmarks for performance-critical code
- Test with real mission data when possible
- Place lengthy or complex tests in the `tests/integration` directory
- Tests in `tests/unit` should use fake data and isolate functionality
- Cover edge cases and error conditions

### Key Commands
- `poetry install` - Install dependencies
- `pytest` - Run tests
- `ruff check` - Lint code
- `ruff format` - Format code
- `spp` - CLI entry point
- `pre-commit run --all` - Run all pre-commit checks

### Mission Support
This library actively supports multiple space missions including IMAP, CLARREO Pathfinder, Libera, CTIM-FD, and MMS-FEEPS. Changes should maintain backward compatibility and consider real-world usage patterns.

## When Contributing
- Understand XTCE/CCSDS standards when modifying parsing logic
- Consider performance implications for large packet streams
- Test against mission-specific packet definitions
- Maintain compatibility with existing mission integrations
- Follow semantic versioning principles