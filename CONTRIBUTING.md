# Contributing to DHL & Deutsche Post Integration

Thank you for your interest in contributing! This document provides guidelines for contributing to this project.

## Table of Contents

- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Code Style](#code-style)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Release Process](#release-process)
- [Architecture Decisions](#architecture-decisions)

## Getting Started

### Prerequisites

- Python 3.11+
- Home Assistant 2024.7+
- [uv](https://github.com/astral-sh/uv) for dependency management
- Git

### Quick Start

```bash
# Clone the repository
git clone https://github.com/huskynarr/hacs-post.git
cd hacs-post

# Install dependencies
uv sync --dev

# Run tests
uv run pytest

# Run linters
uv run ruff check .
uv run mypy custom_components/dhl_de
```

## Development Setup

### Home Assistant Development Environment

1. Create a virtual environment for HA development:
```bash
uv venv --python 3.11 .venv
source .venv/bin/activate
uv pip install homeassistant==2024.12.0
```

2. Set up a test Home Assistant instance:
```bash
mkdir -p /tmp/ha_test/config
hass --config /tmp/ha_test/config --script ensure_config
```

3. Link the custom component:
```bash
ln -s $(pwd)/custom_components/dhl_de /tmp/ha_test/config/custom_components/dhl_de
```

4. Run HA with debug logging:
```bash
hass --config /tmp/ha_test/config --debug
```

## Code Style

This project follows strict code quality standards:

### Python Style
- **Formatter**: `ruff format` (Black-compatible)
- **Linter**: `ruff check` (with all rules enabled)
- **Type Checking**: `mypy --strict`
- **Line Length**: 100 characters
- **Imports**: Sorted with `ruff` (isort-compatible)

### Type Hints
- All public functions must have type hints
- Use `from __future__ import annotations` in all files
- Prefer `typing` module types over built-in generics for compatibility
- No `Any` without justification comment

### Docstrings
- Google-style docstrings for all public classes and functions
- Include Args, Returns, Raises sections
- Document async behavior explicitly

### Async Guidelines
- All I/O operations must be async
- Use `asyncio.timeout()` for external calls
- Properly handle `CancelledError`
- Use `async with` for resource management

## Testing

### Test Structure
```
tests/
├── unit/              # Unit tests (mocked, fast)
│   ├── test_api.py
│   ├── test_coordinator.py
│   ├── test_email_parser.py
│   └── test_sensors.py
├── integration/       # Integration tests (requires HA)
│   └── test_config_flow.py
└── fixtures/          # Test fixtures and mock data
    ├── api_responses/
    └── email_samples/
```

### Running Tests

```bash
# All tests
uv run pytest

# Unit tests only
uv run pytest tests/unit/

# Integration tests only
uv run pytest tests/integration/

# With coverage
uv run pytest --cov=custom_components.dhl_de --cov-report=term-missing

# Specific test
uv run pytest tests/unit/test_api.py::test_track_shipment -v
```

### Test Requirements
- Minimum 90% coverage for new code
- All tests must pass in CI
- Mock external dependencies (API, IMAP, time)
- Use `freezegun` for time-dependent tests

## Pull Request Process

### Before Submitting

1. **Create an issue** first for significant changes
2. **Branch naming**: `feat/`, `fix/`, `chore/`, `docs/`, `refactor/`, `test/`
3. **Commit messages**: Follow [Conventional Commits](https://www.conventionalcommits.org/)
   ```
   feat: add Packstation pickup notifications
   fix: handle API rate limiting correctly
   docs: update README with new sensor entities
   ```
4. **Run all checks locally**:
   ```bash
   uv run ruff check . && uv run ruff format --check . && uv run mypy custom_components/dhl_de && uv run pytest
   ```

### PR Requirements

- [ ] All CI checks pass
- [ ] Coverage maintained or improved
- [ ] CHANGELOG.md updated (under `## Unreleased`)
- [ ] Translations updated (en.json, de.json)
- [ ] Documentation updated if user-facing changes
- [ ] No breaking changes without major version bump

### Review Process

1. Automated checks run (lint, type, test, HACS validation)
2. Maintainer reviews code and architecture
3. Feedback addressed
4. Squash and merge with conventional commit message

## Release Process

This project follows [Semantic Versioning](https://semver.org/).

### Version Bumping

- **Patch** (x.y.Z): Bug fixes, small improvements
- **Minor** (x.Y.z): New features, backward compatible
- **Major** (X.y.z): Breaking changes

### Release Workflow

1. Create release PR with version bump:
   ```bash
   # Update version in manifest.json and hacs.json
   # Update CHANGELOG.md
   git commit -m "chore: release v1.2.3"
   ```

2. Tag and push:
   ```bash
   git tag v1.2.3
   git push origin main --tags
   ```

3. GitHub Actions creates release, publishes to HACS

### Changelog Format

Follow [Keep a Changelog](https://keepachangelog.com/):

```markdown
## [1.2.3] - 2024-01-15
### Added
- New Packstation sensor for pickup notifications
### Changed
- Improved API error handling
### Fixed
- Race condition in coordinator refresh
```

## Architecture Decisions

### Key Design Principles

1. **Carrier-Agnostic Format** — Parcel data follows the ha-parcel-integrations canonical format for cross-carrier compatibility
2. **Coordinator Pattern** — Use DataUpdateCoordinator for efficient polling and entity updates
3. **Config Entry Runtime Data** — Store client/coordinator in typed `ConfigEntry.runtime_data`
4. **Separate Coordinators** — Package tracking and Briefankündigung use independent coordinators
5. **Event-Driven Updates** — Fire HA events for parcel lifecycle changes

### API Client Design

- Single `DhlApiClient` class with async methods
- Automatic retry with exponential backoff
- Proper error types (`DhlApiError`, `DhlAuthError`, `DhlRateLimitError`)
- Sandbox/Production environment switching

### Email Parsing

- Modular shipper pattern (extensible for other carriers)
- Base64 image extraction with size filtering
- Animated GIF generation via Pillow
- Camera entity follows HA camera patterns

### Sensor Lifecycle

- Dynamic sensor creation/removal via `async_add_entities`
- Unique IDs based on config entry + tracking number
- Proper cleanup on unload

## Questions?

Open a [Discussion](https://github.com/huskynarr/hacs-post/discussions) or [Issue](https://github.com/huskynarr/hacs-post/issues).