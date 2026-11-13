# Getting started

This guide explains how to install and begin using `precog-esgf-intake`.

## Installation

Install from the repository:

```bash
pip install git+https://github.com/<organisation>/precog-esgf-intake.git
```

For development:

```bash
git clone https://github.com/<organisation>/precog-esgf-intake.git
cd precog-esgf-intake
pip install -e ".[dev,docs]"
```

## Requirements

- Python 3.10 or newer
- Intake
- `intake-esgf`
- `xarray`
- Network access to ESGF services, where required

## Minimal example

```python
import precog_esgf_intake as pei

# Replace with the package's real public API
# catalog = pei.open_catalog(...)
# dataset = catalog.search(...)
# ds = dataset.to_dataset()
```

## Next steps

```{toctree}
:maxdepth: 1

user_guide/index
examples/index
api/index
```
