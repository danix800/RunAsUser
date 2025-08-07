# Python - Run As User

This project provides a Python utility to run commands as the currently logged-in user from a high-privilege context (e.g., SYSTEM), with full, clean `stdio` redirection.

It is designed to be used both as a command-line tool and as a library in other Python projects.

## Requirements

- Python 3.8+
- Windows Operating System
- `pywin32` library

## Installation

This project is structured as a standard Python package and can be installed using `uv` or `pip`.

From the `run_as_user` directory (where `pyproject.toml` is located), run:

```bash
# Using uv
uv pip install .

# Using pip
pip install .
```

This will install the package and make the `run-as-user` command-line tool available in your environment.

## Usage

**Important**: This tool must be executed from a process running with SYSTEM privileges to function correctly.

### As a Command-Line Tool

The `run-as-user` command allows you to execute any command-line string. It supports piping `stdin`, `stdout`, and `stderr`.

**Basic Example:**

```bash
# Execute a simple command
run-as-user cmd.exe /c "echo Hello from the user's context"
```

**Piping Example:**

```bash
# Pipe data to a command running as the user
echo "some text" | run-as-user findstr "text"
```

**Logging:**

To keep the `stdio` streams clean for piping, all internal logging from the tool itself is suppressed. You can redirect these logs to a file using the `--log-file` argument.

```bash
run-as-user --log-file C:\temp\run-as-user.log cmd.exe /c "whoami"
```

### As a Library

You can also import and use the core functionality directly in your Python code.

The main function is `run_as_current_user`, which can be imported from the `run_as_user` package.

**Library Example:**

```python
from run_as_user import run_as_current_user
import os

def get_user_environment_variables():
    # Command to get environment variables in the user's context
    command = 'cmd.exe /c set'
    
    # Data to pipe to the command's stdin (not needed for this example)
    input_data = None
    
    # Path for logging
    log_path = os.path.join(os.environ.get("TEMP", "C:\\Temp"), "mylog.txt")

    print(f"Running command: '{command}'")
    stdout, stderr = run_as_current_user(
        command,
        input_data=input_data,
        log_file=log_path
    )

    if stderr:
        print(f"An error occurred:\n{stderr.decode('utf-8', errors='ignore')}")
    
    if stdout:
        print("\nUser's Environment Variables:")
        print(stdout.decode('utf-8', errors='ignore'))

if __name__ == "__main__":
    # This script must be run as SYSTEM for this to work
    try:
        get_user_environment_variables()
    except Exception as e:
        print(f"Failed to run: {e}")
        print("Ensure you are running this script from a SYSTEM context.")
