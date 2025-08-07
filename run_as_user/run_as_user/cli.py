import argparse
import sys
from .main import run_as_current_user

def main():
    """
    Command-line interface for the run-as-user utility.
    """
    parser = argparse.ArgumentParser(
        description="Run a command as the currently logged-in user, with stdio redirection.",
        epilog="This tool is intended to be run from a high-privilege context (e.g., SYSTEM)."
    )
    parser.add_argument(
        "command",
        nargs='+',
        help="The command to execute, along with its arguments."
    )
    parser.add_argument(
        "--no-wait",
        action="store_false",
        dest="wait",
        help="Do not wait for the command to complete."
    )
    parser.add_argument(
        "--log-file",
        type=str,
        help="Path to a file for logging status messages."
    )

    args = parser.parse_args()

    # Join the command and its arguments into a single string
    full_command = " ".join(args.command)

    # Read from stdin if data is being piped
    input_data = None
    if not sys.stdin.isatty():
        input_data = sys.stdin.buffer.read()

    stdout_data, stderr_data = run_as_current_user(
        full_command, 
        input_data=input_data, 
        wait=args.wait,
        log_file=args.log_file
    )

    if stdout_data:
        sys.stdout.buffer.write(stdout_data)
    
    if stderr_data:
        sys.stderr.buffer.write(stderr_data)

    if stdout_data is None and stderr_data is None and args.wait:
        # This indicates an error occurred in run_as_current_user
        sys.exit(1)

if __name__ == "__main__":
    main()
