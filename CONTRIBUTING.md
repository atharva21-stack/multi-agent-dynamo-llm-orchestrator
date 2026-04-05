# Contributing to agent-inference-stack

Thank you for your interest in contributing!

## Development Setup

```bash
# Clone the repository
git clone https://github.com/your-org/agent-inference-stack.git
cd agent-inference-stack

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dev dependencies
pip install -r requirements-dev.txt

# Copy env template
cp .env.example .env
# Edit .env with your values

# Run tests
make test
```

## Code Standards

- **Python 3.10+** with full type hints
- **Black** for formatting (`make format`)
- **isort** for import sorting
- **mypy** for type checking (`make typecheck`)
- **pylint** for linting (`make lint`)
- **pytest** for testing (`make test`)
- Docstrings on all public classes and functions
- 80%+ test coverage required

## Pull Request Process

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Make your changes with tests
4. Run `make check` (lint + typecheck + test)
5. Submit a PR with a clear description

## Architecture

See [docs/architecture.md](docs/architecture.md) for system design.
