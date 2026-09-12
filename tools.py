
import os
import subprocess

WORKSPACE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "workspace")
)


def get_safe_path(file_path: str) -> str:
    if not file_path:
        raise ValueError("File path cannot be empty.")

    if os.path.isabs(file_path):
        raise ValueError("Absolute paths are not allowed.")

    normalized = os.path.normpath(file_path)

    if normalized == ".." or normalized.startswith(".." + os.sep):
        raise ValueError("Path traversal is not allowed.")

    full_path = os.path.abspath(
        os.path.join(WORKSPACE, normalized)
    )

    workspace_root = os.path.abspath(WORKSPACE)

    if not (
        full_path == workspace_root
        or full_path.startswith(workspace_root + os.sep)
    ):
        raise ValueError("Access outside workspace is not allowed.")

    return full_path


def list_files(path: str = ""):
    try:
        target_dir = WORKSPACE

        if path:
            target_dir = get_safe_path(path)

        if not os.path.isdir(target_dir):
            return f"ERROR: '{path}' is not a directory."

        files = []

        for root, dirs, filenames in os.walk(target_dir):
            dirs[:] = [
                d
                for d in dirs
                if d not in {
                    ".git",
                    "__pycache__",
                    ".venv",
                    "venv",
                    "myenv"
                }
            ]

            for filename in filenames:
                full_path = os.path.join(root, filename)
                relative_path = os.path.relpath(
                    full_path,
                    WORKSPACE
                )
                files.append(
                    relative_path.replace(os.sep, "/")
                )

        files.sort()

        if not files:
            return "Workspace is empty."

        return "\n".join(files)

    except Exception as e:
        return f"ERROR: {str(e)}"


def read_file(file_path: str):
    try:
        safe_path = get_safe_path(file_path)

        if not os.path.isfile(safe_path):
            return f"ERROR: '{file_path}' is not a file."

        with open(
            safe_path,
            "r",
            encoding="utf-8"
        ) as file:
            content = file.read()

        max_output = 20000

        if len(content) > max_output:
            content = (
                content[:max_output]
                + "\n\n[File content truncated.]"
            )

        return content

    except Exception as e:
        return f"ERROR: {str(e)}"


def write_file(file_path: str, content: str):
    try:
        safe_path = get_safe_path(file_path)

        parent = os.path.dirname(safe_path)
        os.makedirs(parent, exist_ok=True)

        with open(
            safe_path,
            "w",
            encoding="utf-8"
        ) as file:
            file.write(content)

        return (
            f"File '{file_path}' "
            "written successfully."
        )

    except Exception as e:
        return f"ERROR: {str(e)}"


BLOCKED_COMMANDS = {
    "del",
    "erase",
    "rmdir",
    "rd",
    "rm",
    "shred",
    "format",
    "diskpart",
    "shutdown",
    "restart-computer",
    "remove-item",
    "reg",
    "regedit",
    "takeown",
    "icacls",
    "cipher"
}


BLOCKED_GIT_COMMANDS = {
    "reset",
    "clean",
    "checkout",
    "restore",
    "rebase",
    "push",
    "pull"
}


def get_first_command(command: str):
    command = command.strip()

    if not command:
        return ""

    return command.split()[0].lower()


def is_command_safe(command: str):
    if not command or not command.strip():
        return False, "Command cannot be empty."

    command_lower = command.lower().strip()

    dangerous_patterns = [
        "&&",
        "||",
        ">",
        ">>",
        "|",
        "$(",
        "`",
        "\n",
        "\r"
    ]

    for pattern in dangerous_patterns:
        if pattern in command_lower:
            return False, (
                f"Blocked shell operator: {pattern}"
            )

    first_command = get_first_command(command_lower)

    if first_command in BLOCKED_COMMANDS:
        return False, (
            f"Blocked command: {first_command}"
        )

    if first_command == "git":
        parts = command_lower.split()

        if (
            len(parts) > 1
            and parts[1] in BLOCKED_GIT_COMMANDS
        ):
            return False, (
                f"Blocked git operation: {parts[1]}"
            )

    return True, ""


def run_command(command: str):
    try:
        safe, reason = is_command_safe(command)

        if not safe:
            return (
                "ERROR: Command blocked for safety. "
                + reason
            )

        command = command.replace(
            "python3",
            "python"
        )

        if (
            command.startswith("./")
            and command.endswith(".py")
        ):
            command = "python " + command[2:]

        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=WORKSPACE
        )

        stdout = result.stdout.strip()
        stderr = result.stderr.strip()

        max_output = 10000

        if len(stdout) > max_output:
            stdout = (
                stdout[:max_output]
                + "\n\n[Output truncated.]"
            )

        if len(stderr) > max_output:
            stderr = (
                stderr[:max_output]
                + "\n\n[Error output truncated.]"
            )

        output_parts = []

        if stdout:
            output_parts.append(stdout)

        if stderr:
            output_parts.append(
                "ERROR:\n" + stderr
            )

        if not output_parts:
            if result.returncode == 0:
                return "Command executed successfully."

            return (
                "ERROR: Command exited with code "
                + str(result.returncode)
                + "."
            )

        output = "\n".join(output_parts)

        if result.returncode != 0:
            output = (
                "ERROR: Command exited with code "
                + str(result.returncode)
                + ".\n"
                + output
            )

        return output

    except subprocess.TimeoutExpired:
        return (
            "ERROR: Command timed out "
            "after 30 seconds."
        )

    except Exception as e:
        return f"ERROR: {str(e)}"


def git_status():
    try:
        result = subprocess.run(
            ["git", "status", "--short"],
            cwd=os.path.abspath(
                os.path.join(WORKSPACE, "..")
            ),
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return (
                "ERROR: "
                + result.stderr.strip()
            )

        output = result.stdout.strip()

        if not output:
            return "Working tree is clean."

        return output

    except Exception as e:
        return f"ERROR: {str(e)}"


def git_diff():
    try:
        result = subprocess.run(
            [
                "git",
                "diff",
                "--",
                "workspace"
            ],
            cwd=os.path.abspath(
                os.path.join(WORKSPACE, "..")
            ),
            capture_output=True,
            text=True,
            timeout=30
        )

        if result.returncode != 0:
            return (
                "ERROR: "
                + result.stderr.strip()
            )

        output = result.stdout.strip()

        if not output:
            return "No changes in workspace."

        max_output = 20000

        if len(output) > max_output:
            output = (
                output[:max_output]
                + "\n\n[Diff truncated.]"
            )

        return output

    except Exception as e:
        return f"ERROR: {str(e)}"


TOOLS = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "run_command": run_command,
    "git_status": git_status,
    "git_diff": git_diff
}
