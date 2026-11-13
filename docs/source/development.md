# Development

This page explains how to set up a development environment, run tests, build
documentation, and contribute changes.

## Development installation

```bash
git clone https://github.com/<organisation>/precog-esgf-intake.git
cd precog-esgf-intake
git checkout Dev_Docs
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,docs]"
```

## Running tests

```bash
pytest
```

## Building documentation locally

```bash
cd docs
make html
```

The built site will be available at:

```text
docs/build/html/index.html
```

## Documentation conventions

- Write narrative pages in MyST Markdown.
- Use NumPy-style docstrings for public functions, classes, and methods.
- Keep examples executable wherever possible.
- Cross-reference API objects rather than duplicating their descriptions.
- Add new user-facing behaviour to the changelog.
