# Contributing to CM-Dashboard

First off, thank you for considering contributing to the **CM-Dashboard (Complaint Intelligence System)**! It's people like you that make open-source tools powerful and accessible.

This document outlines the process for contributing to the project, setting up the local environment, and the coding standards we enforce to keep the system production-grade.

---

## 🚀 How Can I Contribute?

### 1. Reporting Bugs
If you find a bug in the Multi-Agent System, the FAISS memory layer, or anywhere else:
- Open a GitHub Issue using the **Bug Report** template.
- Provide a detailed explanation of the bug.
- Include logs from `logs/system.log` or `logs/error.log` if applicable.

### 2. Suggesting Enhancements
Want to add a new Agent type or improve the DBSCAN clustering logic?
- Open an Issue using the **Feature Request** template.
- Clearly describe the use case, the architectural impact, and how it integrates with the existing pipeline (e.g., does it interact with the `AsyncQueue`?).

---

## 🛠 Local Development Setup

To contribute code, you'll need to run the CM-Dashboard locally.

### Prerequisites
- Python 3.9+
- Git

### Installation Steps
1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:
   ```bash
   git clone git@github.com:YOUR_USERNAME/CM-Dashboard.git
   cd CM-Dashboard
   ```
3. **Set up a Virtual Environment**:
   ```bash
   python -m venv .venv
   # On Windows:
   .venv\Scripts\activate
   # On macOS/Linux:
   source .venv/bin/activate
   ```
4. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
5. **Initialize Directories**:
   Ensure `logs/` and `outputs/` exist in the root to prevent pipeline crashes.

---

## 🌿 Git Workflow & Branching Strategy

We follow a structured branching model to keep the `main` branch stable.

1. Create a branch from `main` with a descriptive prefix:
   - `feat/your-feature-name` (For new features or agents)
   - `fix/issue-description` (For bug fixes)
   - `docs/update-readme` (For documentation)
   - `test/add-unit-tests` (For adding tests)
   - `refactor/clean-up-pipeline` (For code refactoring)

2. Commit your changes using semantic commit messages:
   - **Good**: `feat(agents): add language translation agent for non-English complaints`
   - **Bad**: `added new agent`

---

## 💻 Coding Standards & Rules

To ensure CM-Dashboard remains a robust, production-ready system, all PRs must adhere to the following standards:

1. **PEP8 Compliance**: 
   - All Python code must be formatted using `black` and linted with `flake8`.
2. **Type Hinting**:
   - Every function and class method **MUST** include Python type hints (e.g., `def process(text: str) -> Dict[str, Any]:`).
3. **Modularity (The Golden Rule)**:
   - Do not build monolithic functions. If you are extending the AI pipeline, create an isolated Agent in `app/services/agents/` and register it with the `PipelineManager`.
4. **Logging**:
   - Never use `print()`. Always use the standard Python `logging` module to pipe outputs to `logs/system.log` or `logs/error.log`.

---

## 🧪 Testing Your Changes

Before submitting a Pull Request, you **must** ensure the pipeline hasn't broken.

1. **Run the End-to-End Validation CLI**:
   ```bash
   python run_pipeline.py --test
   ```
2. **Verify the Output**:
   - Ensure the CLI prints `✅ E2E Testing Completed`.
   - Check `outputs/decisions.json` to verify that your new logic correctly outputted a structured JSON decision.
   - If your PR modifies the Machine Learning pipeline (`app/ml/`), ensure the metrics (`accuracy`, `f1_score`) in `outputs/metrics.json` have not regressed.

---

## 📥 Pull Request Process

1. Push your branch to your forked repository.
2. Open a Pull Request against the `main` branch of the upstream repository.
3. Your PR description must include:
   - A summary of the changes.
   - The Issue number it resolves (e.g., `Fixes #42`).
   - Confirmation that you ran `run_pipeline.py --test`.
4. Request a review from the core maintainers. Once approved, it will be merged via Squash and Merge.

Thank you for contributing to the future of Complaint Intelligence! 🎉
