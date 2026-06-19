# Contributing to CM-Dashboard

Thank you for your interest in improving the CM-Dashboard AI System!

## Contribution Workflow
1. **Fork** the repository.
2. **Branch** from `main` (`git checkout -b feat/your-feature-name`).
3. **Commit** your changes using standard Git naming conventions.
4. **Push** your branch and open a **Pull Request (PR)**.

## Coding Standards
- **PEP8 Compliance**: All Python code must adhere to PEP8. Use `black` or `flake8` for formatting.
- **Type Hints**: All functions and methods MUST include Python type hints (`from typing import Dict, List, Any`, etc.).
- **Modularity**: Do not build monoliths. Keep the Multi-Agent services decoupled.

## Git Naming Conventions
Prefix your commits to clearly signal intent:
- `feat:` for new features (e.g., `feat(agents): add language detection agent`)
- `fix:` for bug fixes
- `docs:` for documentation updates
- `test:` for adding/updating tests
- `refactor:` for code restructuring without behavioral changes

## Pull Request Requirements
Before your PR can be merged, it must include:
- **Tests**: Validated via `run_pipeline.py --test` with normal, edge, and unseen cases.
- **Logs**: Do not break the logging infrastructure. All output must properly pipe to `logs/system.log`.
- **Description**: A comprehensive PR description outlining what was changed and why.
