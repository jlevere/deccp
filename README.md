# deccp

Extract and decompile `code.ccp` into a clean Python source tree.

`code.ccp` is found in the eveonline client files.

This tool takes a CCP game client's `code.ccp` archive (a ZIP of `.pyj` blobs), decompresses and decompiles the bytecode, and writes out the resulting Python source files.

## Features

- Decompresses `.pyj` blobs from a `code.ccp` archive
- Decompiles Python bytecode using [uncompyle6](https://github.com/rocky/python-uncompyle6) and [xdis](https://github.com/rocky/python-xdis)
- Parallel processing for speed
- Outputs decompilation errors to a JSON file for review

## Requirements

- Python > 3.11
- [`uv`](https://github.com/astral-sh/uv) (for dependency management)

## Installation

Install the project and its dependencies in editable mode:

```sh
uv venv
uv sync
```

## Development Environment (Nix Flakes)

If you use [Nix flakes](https://nixos.wiki/wiki/Flakes):

```sh
nix develop
```

This provides a shell with Python 3.12, `uv`, and all project dependencies available inside a `.venv`.

## Usage

You can run the tool via the CLI:

```sh
uv run python -m deccp.main <path/to/code.ccp> [--out <output_dir>] [--jobs <num_workers>]
```

Or, if installed as an entry point:

```sh
deccp <path/to/code.ccp> [--out <output_dir>] [--jobs <num_workers>]
```

- `<path/to/code.ccp>`: Path to the CCP archive (a ZIP of `.pyj` files)
- `--out <output_dir>`: Output directory for the `client_code/` tree (default: same directory as the ZIP)
- `--jobs <num_workers>`: Number of parallel decompile workers (default: 4)

### Example

```sh
deccp code.ccp --out ./output --jobs 8
```

## Output

- Decompiled Python files are written to a `client_code/` directory inside your chosen output path.
- Any decompilation failures are logged in `decompile_errors.json`.
