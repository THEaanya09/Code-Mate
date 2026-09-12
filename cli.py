import argparse
import sys

from agent import run_agent


VERSION = "1.0.0"


def print_banner():
    print()
    print("╔══════════════════════════════════════╗")
    print("║              CodeMate                ║")
    print("║         [    By AANYA    ]           ║")
    print("╚══════════════════════════════════════╝")
    print()


def run_task(task):
    print_banner()
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

    if args.task:
        task = " ".join(args.task)
        run_task(task)
        return

    print_banner()
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