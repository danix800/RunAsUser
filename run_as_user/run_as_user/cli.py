import argparse
import sys
from .main import run_as_current_user

def main():
    """
    Command-line interface for the run-as-user utility.
    """
    parser = argparse.ArgumentParser(
        description="Run a command as the currently logged-in user with real-time, interactive stdio.",
        epilog="This tool is intended to be run from a high-privilege context (e.g., SYSTEM)."
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="The command to execute, along with its arguments."
    )
    parser.add_argument(
        "--log-file",
        type=str,
        help="Path to a file for logging status messages."
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Join the command and its arguments into a single string
    full_command = " ".join(args.command)

    try:
        exit_code = run_as_current_user(
            full_command,
            log_file=args.log_file
        )
        sys.exit(exit_code)
    except Exception as e:
        # Log critical errors to stderr if no log file is specified
        log_dest = open(args.log_file, "a") if args.log_file else sys.stderr
        print(f"Failed to start process: {e}", file=log_dest)
        if args.log_file:
            log_dest.close()
        sys.exit(1)

if __name__ == "__main__":
    main()
