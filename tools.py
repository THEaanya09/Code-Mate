import os
import shlex
import subprocess

from config import WORKSPACE


# ========================================
# Workspace Path Safety
# ========================================

def get_safe_path(path):
    """
    Convert a relative workspace path into an
    absolute safe path.

    Prevents access outside the workspace.
    """

    path = str(path).strip().strip('"').strip("'")

    workspace_root = os.path.abspath(WORKSPACE)

    full_path = os.path.abspath(
        os.path.join(
            workspace_root,
            path
        )
    )

    try:

        common_path = os.path.commonpath(
            [
                workspace_root,
                full_path
            ]
        )

    except ValueError:

        raise ValueError(
            "Access outside workspace is not allowed."
        )

    if common_path != workspace_root:

        raise ValueError(
            "Access outside workspace is not allowed."
        )

    return full_path


# ========================================
# List Files
# ========================================

def list_files(path: str = ".") -> str:
    """
    List files and directories inside the workspace.

    Args:
        path: Relative directory path.

    Returns:
        List of files and directories.
    """

    try:

        safe_path = get_safe_path(path)

        if not os.path.isdir(safe_path):

            return (
                f"ERROR: '{path}' "
                "is not a directory."
            )

        files = []

        for item in sorted(
            os.listdir(safe_path)
        ):

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

    except Exception as e:

        return f"ERROR: {str(e)}"


# ========================================
# Read File
# ========================================

def read_file(file_path: str) -> str:
    """
    Read the contents of a specific file.

    Args:
        file_path: Relative path of the file.

    Returns:
        File contents.
    """

    try:

        safe_path = get_safe_path(
            file_path
        )

        if not os.path.isfile(safe_path):

            return (
                f"ERROR: '{file_path}' "
                "is not a file."
            )

        with open(
            safe_path,
            "r",
            encoding="utf-8"
        ) as file:

            return file.read()

    except UnicodeDecodeError:

        return (
            f"ERROR: '{file_path}' "
            "is not a UTF-8 text file."
        )

    except Exception as e:

        return f"ERROR: {str(e)}"


# ========================================
# Write File
# ========================================

def write_file(
    file_path: str,
    content: str
) -> str:
    """
    Create or modify a file inside the workspace.

    Args:
        file_path: Relative path of the file.
        content: Complete file content.

    Returns:
        Success or error message.
    """

    try:

        safe_path = get_safe_path(
            file_path
        )

        parent = os.path.dirname(
            safe_path
        )

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

        return (
            f"File '{file_path}' "
            "written successfully."
        )

    except Exception as e:

        return f"ERROR: {str(e)}"


# ========================================
# Command Security
# ========================================

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
    "cipher",
}


BLOCKED_GIT_COMMANDS = {
    "reset",
    "clean",
    "checkout",
    "restore",
    "rebase",
    "push",
    "pull",
}


def get_first_command(command):
    """
    Extract the first executable from a command.
    """

    try:

        parts = shlex.split(
            command,
            posix=False
        )

        if not parts:

            return ""

        executable = parts[0]

        executable = os.path.basename(
            executable
        )

        executable = (
            executable
            .lower()
            .strip('"')
            .strip("'")
        )

        if executable.endswith(".exe"):

            executable = executable[:-4]

        return executable

    except Exception:

        return ""


def is_command_safe(command):
    """
    Perform basic safety checks on a shell command.

    Returns:
        (True, "") if safe.
        (False, reason) if blocked.
    """

    if not isinstance(
        command,
        str
    ):

        return (
            False,
            "Command must be a string."
        )

    command_lower = command.lower().strip()

    if not command_lower:

        return (
            False,
            "Empty command is not allowed."
        )

    # ====================================
    # Block shell chaining / redirection
    # ====================================

    dangerous_patterns = [
        "&&",
        "||",
        ">",
        ">>",
        "|",
        "$(",
        "`",
        "\n",
        "\r",
    ]

    for pattern in dangerous_patterns:

        if pattern in command_lower:

            return (
                False,
                "Command contains blocked "
                f"shell operator: {pattern}"
            )

    # ====================================
    # Identify executable
    # ====================================

    executable = get_first_command(
        command
    )

    if not executable:

        return (
            False,
            "Could not determine command."
        )

    # ====================================
    # Block dangerous commands
    # ====================================

    if executable in BLOCKED_COMMANDS:

        return (
            False,
            f"Command '{executable}' "
            "is blocked for safety."
        )

    # ====================================
    # Git safety
    # ====================================

    if executable == "git":

        try:

            parts = shlex.split(
                command,
                posix=False
            )

            if len(parts) > 1:

                git_operation = (
                    parts[1]
                    .lower()
                    .strip('"')
                    .strip("'")
                )

                if (
                    git_operation
                    in BLOCKED_GIT_COMMANDS
                ):

                    return (
                        False,
                        f"Git operation "
                        f"'{git_operation}' "
                        "is blocked for safety."
                    )

        except Exception:

            return (
                False,
                "Could not safely parse "
                "Git command."
            )

    return True, ""


# ========================================
# Run Command
# ========================================

def run_command(command: str) -> str:
    """
    Execute a command inside the workspace
    after basic safety validation.

    Args:
        command: Command to execute.

    Returns:
        Command output or error.
    """

    try:

        # ====================================
        # Safety check
        # ====================================

        safe, reason = is_command_safe(
            command
        )

        if not safe:

            return (
                "ERROR: Command blocked "
                f"for safety. {reason}"
            )

        # ====================================
        # Normalize Python commands
        # ====================================

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

        # ====================================
        # Execute command
        # ====================================

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

        # ====================================
        # Limit output size
        # ====================================

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

        # ====================================
        # Build response
        # ====================================

        output_parts = []

        if stdout:

            output_parts.append(
                stdout
            )

        if stderr:

            output_parts.append(
                "ERROR:\n"
                + stderr
            )

        if not output_parts:

            if result.returncode == 0:

                return (
                    "Command executed successfully."
                )

            return (
                "ERROR: Command exited "
                f"with code {result.returncode}."
            )

        output = "\n".join(
            output_parts
        )

        if result.returncode != 0:

            output = (
                "ERROR: Command exited "
                f"with code {result.returncode}.\n"
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


# ========================================
# Git Status
# ========================================

def git_status() -> str:
    """
    Show Git status for files inside the workspace.

    Returns:
        Git status output.
    """

    try:

        repo_root = os.path.abspath(
            os.path.join(
                WORKSPACE,
                ".."
            )
        )

        result = subprocess.run(
            [
                "git",
                "status",
                "--short",
                "--",
                "workspace"
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=repo_root
        )

        if result.returncode != 0:

            return (
                "ERROR: Git status failed.\n"
                + result.stderr.strip()
            )

        output = result.stdout.strip()

        if not output:

            return (
                "Git working tree is clean."
            )

        return output

    except FileNotFoundError:

        return (
            "ERROR: Git is not installed "
            "or is not available in PATH."
        )

    except subprocess.TimeoutExpired:

        return (
            "ERROR: Git status timed out."
        )

    except Exception as e:

        return f"ERROR: {str(e)}"


# ========================================
# Git Diff
# ========================================

def git_diff() -> str:
    """
    Show Git diff for tracked files
    inside the workspace.

    Returns:
        Git diff output.
    """

    try:

        repo_root = os.path.abspath(
            os.path.join(
                WORKSPACE,
                ".."
            )
        )

        result = subprocess.run(
            [
                "git",
                "diff",
                "--",
                "workspace"
            ],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=repo_root
        )

        if result.returncode != 0:

            return (
                "ERROR: Git diff failed.\n"
                + result.stderr.strip()
            )

        output = result.stdout.strip()

        if not output:

            return (
                "No tracked changes found "
                "in the workspace."
            )

        return output

    except FileNotFoundError:

        return (
            "ERROR: Git is not installed "
            "or is not available in PATH."
        )

    except subprocess.TimeoutExpired:

        return (
            "ERROR: Git diff timed out."
        )

    except Exception as e:

        return f"ERROR: {str(e)}"


# ========================================
# Tool Registry
# ========================================

TOOLS = {
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
    "run_command": run_command,
    "git_status": git_status,
    "git_diff": git_diff
}