# precog-esgf-intake 🦑

Automated discovery, validation, and optimized download management of Earth system model data
from [Earth System Grid Federation](https://esgf-ui.ceda.ac.uk/search) nodes.

## Overview
This repository contains scripts and workflows to automate bulk discovery, file checking, validation and download of
datasets from ESGF archives.
It is designed to support climate and oceanographic analyses that require consistent, reproducible access to large model
datasets.

## Features

- Definition of ESGF search criteria by modifying a [`search_criteria.toml`](scripts/search_criteria.toml) configuration file.
- Automated search through the ESGF catalogue using project, variable, experiment, and temporal filters (inherited 
  from [intake-esgf](https://github.com/esgf2-us/intake-esgf)).
- Ensemble-aware screening mode for selecting one validated `piControl` anchor branch and retaining all compatible `Historical` ensemble members on the same grid.
- Single-branch screening mode for selecting one internally consistent `piControl/Historical` branch pairing per 
  accepted model/grid.
- Combined-variable screening for retaining models that provide all requested variables simultaneously across both 
`piControl` and `historical` runs, producing a single shortlist for downstream download.
- Verification and logging of continuity of date stamps and availability of `piControl` and `Historical` runs on 
  consistent grids (e.g., regular grid `gr` and native grid `gn`).
- Export of simple Dataframes for realised ESGF catalogue searches.
- Verification of server responses and flagging shortlisted ESM outputs as 'Downloadable'.
- Parallelized URL checks for fastest connection in case same data are available across different nodes.
- Parallel batch downloading of files from multiple ESGF nodes with retry and integrity checks.
- Parallel batch search and download of grid cell measures (e.g., `areacello` and `volcello`) with archive snapshot of
  relaxed regex matches for later inspection.
- Local directory layout optimised for downstream analysis.
- Example Jupyter notebook workflow covering TOML setup, catalogue screening, and download preparation.

## Installation

These instructions assume you have **Python 3.12+** installed and available as `python` or `python3` on your system.

### 1. Clone the repository

```bash
git clone https://github.com/precog-ocean/precog-esgf-intake.git
cd precog-esgf-intake
````

### 2. Create a virtual environment (named `venv`)

```bash
python3 -m venv .venv
````

Make sure your python version is >3.12.
You can check which python you have installed on your machine by typing `python` followed by `TAB` a few times. It will
list your python versions.

The argument `.venv` means a hidden directory will be created under the project directory you are in, where python and
its dependencies will be installed (i.e., `~/precog-esgf-intake/.venv`).

### 3. Activate it

```bash
source .venv/bin/activate
```

When activation succeeds, your shell prompt will usually show the environment name in parentheses, for example
`(.venv)...`

### 4. Upgrade pip (recommended)

Inside the activated virtual environment, upgrade `pip`:

```bash
python -m pip install --upgrade pip
```

### 5. Install dependencies

```bash 
pip install -r requirements.txt
```

## Checking installation

Make sure that you have activated the python virtual environment. Then run:

```bash 
python3 tests/test_install.py
```

If you see the PREGOC logo followed by Hellen, the vampire squid from hell, being printed on the terminal as shown in
the example below, then you probably installed things correctly.
![image](misc_images/test_install_screenshot.png)

## Repository structure
```                
precog-esgf-intake/
├─ intake_esgf_mods/     # Adaptations to "esgf-intake" catalogue functionality
├─ misc_images/          # Images (these are renderered as ASCII art headers and footers in the CLI)
├─ paper/                # JOSS submission files and configs for automated pdf draft generator through GitHub actions.
├─ scripts/              # Main workflows to be run as command line scripts (see notebooks for examples)
├─ notebooks/            # Guided tutorials
└─ tests/                # Unit tests for core functionality
```

## Workflow
A Jupyter notebook [Workflow_Example_POCflux.ipynb](notebooks/Workflow_Example_POCflux.ipynb) is provided, which demonstrates how
to find amongst CMIP6 models those that contain both ```piControl``` and ```historical``` outputs for:

```
 'epc100' : Downward Flux of Particulate Organic Carbon at 100m depth [mol m-2 s-1]
 'expc' :   Downward Flux of Particulate Organic Carbon fully-resolved at depth [mol m-2 s-1]
```

This self-guided notebook demonstrates a compound search, an exemple add-on function for screening ESGF catalogue hits,
how to instanciate the download manager and how to automatically fetch corresponding ocean grid cell measure variables
```areacello``` and ```volcello``` for the selected models.
