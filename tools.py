import os
import subprocess

from config import WORKSPACE


def get_safe_path(path):

    path = path.strip().strip('"').strip("'")

    full_path = os.path.abspath(
        os.path.join(WORKSPACE, path)
    )

    if os.path.commonpath(
        [WORKSPACE, full_path]
    ) != WORKSPACE:

        raise ValueError(
            "Access outside workspace is not allowed."
        )

    return full_path


def read_file(file_path):

    safe_path = get_safe_path(file_path)

    if not os.path.isfile(safe_path):
        return f"ERROR: '{file_path}' is not a file."

    with open(
        safe_path,
        "r",
        encoding="utf-8"
    ) as file:

        return file.read()


def write_file(file_path, content):

    safe_path = get_safe_path(file_path)

    parent = os.path.dirname(safe_path)

    os.makedirs(
        parent,
        exist_ok=True
    )

    with open(
        safe_path,
        "w",
        encoding="utf-8"
    ) as file:

        file.write(content)

    return f"File '{file_path}' written successfully."


def run_command(command):

    try:

        dangerous_commands = [
            "del ",
            "rmdir ",
            "rm ",
            "format ",
            "shutdown",
            "restart-computer",
            "remove-item",
            "diskpart",
        ]

        command_lower = command.lower()

        for dangerous in dangerous_commands:

            if dangerous in command_lower:

                return (
                    f"ERROR: Command blocked for safety: "
                    f"{command}"
                )

        command = command.replace(
            "python3",
            "python"
        )

        if (
            command.startswith("./")
            and command.endswith(".py")
        ):

            command = (
                "python "
                + command[2:]
            )

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=WORKSPACE
        )

        output = result.stdout

        if result.stderr:

            output += (
                f"\nERROR:\n"
                f"{result.stderr}"
            )

        return output.strip()

    except subprocess.TimeoutExpired:

        return (
            "ERROR: Command timed out "
            "after 30 seconds."
        )

    except Exception as e:

        return f"ERROR: {str(e)}"


def list_files(path="."):

    safe_path = get_safe_path(path)

    if not os.path.isdir(safe_path):

        return (
            f"ERROR: '{path}' "
            f"is not a directory."
        )

    files = []

    for item in sorted(os.listdir(safe_path)):

        full_path = os.path.join(
            safe_path,
            item
        )

        if os.path.isdir(full_path):

            files.append(
                f"[DIR] {item}"
            )

        else:

            files.append(
                f"[FILE] {item}"
            )

    if not files:

        return "Workspace is empty."

    return "\n".join(files)


def git_status():

    try:

        result = subprocess.run(
            [
                "git",
                "status",
                "--short"
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=WORKSPACE
        )

        if result.returncode != 0:

            return (
                "ERROR: Git status failed.\n"
                + result.stderr.strip()
            )

        output = result.stdout.strip()

        if not output:

            return "Git working tree is clean."

        return output

    except FileNotFoundError:

        return (
            "ERROR: Git is not installed "
            "or is not available in PATH."
        )

    except subprocess.TimeoutExpired:

        return (
            "ERROR: Git command timed out."
        )

    except Exception as e:

        return f"ERROR: {str(e)}"


TOOLS = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "run_command": run_command,
    "git_status": git_status
}