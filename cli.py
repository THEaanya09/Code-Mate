import argparse
import getpass
import sys

from agent import run_agent
from config import (
    DEFAULT_MODEL,
    get_api_key,
    get_model,
    save_config,
)


VERSION = "1.0.3"


def print_banner():
    print()
    print("╔══════════════════════════════════════╗")
    print("║              CodeMate                ║")
    print("║         [    By AANYA    ]           ║")
    print("╚══════════════════════════════════════╝")
    print()


def setup_api_key():
    """
    Ask for the Groq API key on first use and save it globally.
    """

    api_key = get_api_key()

    if api_key:
        return api_key

    print("Groq API key is not configured.")
    print()
    print("You only need to do this once.")
    print("Your key will be saved in:")
    print("~/.codemate/.env")
    print()

    try:
        api_key = getpass.getpass("Enter your Groq API key: ").strip()
    except KeyboardInterrupt:
        print("\nSetup cancelled.")
        sys.exit(130)

    if not api_key:
        print("\nError: API key cannot be empty.")
        sys.exit(1)

    save_config(
        api_key=api_key,
        model=DEFAULT_MODEL
    )

    print()
    print("✓ API key saved.")
    print()

    return api_key


def run_task(task):
    print_banner()

    # Ensure first-run configuration exists before starting the agent.
    setup_api_key()

    print(f"Task: {task}")
    print()

    try:
        result = run_agent(task)

        print()
        print("─" * 50)
        print("✓ TASK COMPLETED")
        print("─" * 50)
        print()
        print(result)
        print()

    except KeyboardInterrupt:
        print("\n✗ Task cancelled.")
        sys.exit(130)

    except Exception as error:
        print(f"\n✗ CodeMate error: {error}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        prog="codemate",
        description="AI-powered terminal coding agent."
    )

    parser.add_argument(
        "task",
        nargs="*",
        help="Task for CodeMate to perform."
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"CodeMate {VERSION}"
    )

    args = parser.parse_args()

    # --version / --help should work without API configuration.
    if args.task:
        task = " ".join(args.task).strip()

        if task:
            run_task(task)

        return

    print_banner()

    setup_api_key()

    print("Enter your coding task.")
    print("Type 'exit' or 'quit' to close CodeMate.")
    print()

    while True:
        try:
            task = input("codemate> ").strip()

        except KeyboardInterrupt:
            print("\n")
            break

        if not task:
            continue

        if task.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        run_task(task)


if __name__ == "__main__":
    main()