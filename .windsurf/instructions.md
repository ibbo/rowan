# Windsurf Development Instructions

## Python Environment

This project uses **uv** for Python dependency management and virtual environment handling.

### Running Python Scripts

Always use `uv run` to execute Python scripts in this project:

```bash
# Instead of: python script.py
# Use:
uv run python script.py

# Or directly:
uv run script.py
```

### Common Commands

```bash
# Run the main application
uv run python main.py

# Run the Gradio web interface
uv run python gradio_app.py

# Run the MCP server
uv run python mcp_scddb_server.py

# Test scripts
uv run python test_scddb_mcp_client.py
uv run python test_name_search.py

# Database operations
uv run python refresh_scddb.py
uv run python explore_scddb.py
uv run python build_views.py
```

### Installing Dependencies

```bash
# Add a new dependency
uv add package-name

# Install from pyproject.toml
uv sync

# Development dependencies
uv add --dev package-name
```

### Environment Management

The project uses uv's built-in virtual environment management. No need to manually activate/deactivate environments when using `uv run`.

### IDE Configuration

If your IDE needs to know the Python interpreter path:
```bash
uv run which python
```

This will show the path to the Python interpreter in the uv-managed virtual environment.
