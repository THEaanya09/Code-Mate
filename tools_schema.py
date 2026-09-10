TOOLS_SCHEMA = [

    {
        "name": "list_files",
        "description": (
            "List files and directories inside "
            "the workspace."
        ),
        "arguments": {
            "path": "string"
        }
    },

    {
        "name": "read_file",
        "description": (
            "Read the contents of a specific file."
        ),
        "arguments": {
            "file_path": "string"
        }
    },

    {
        "name": "write_file",
        "description": (
            "Create or modify a file."
        ),
        "arguments": {
            "file_path": "string",
            "content": "string"
        }
    },

    {
        "name": "run_command",
        "description": (
            "Execute a command inside the workspace."
        ),
        "arguments": {
            "command": "string"
        }
    },

    {
        "name": "git_status",
        "description": (
            "Show the current Git working tree status."
        ),
        "arguments": {}
    },

    {
        "name": "git_diff",
        "description": (
            "Show the Git diff for tracked files "
            "inside the workspace."
        ),
        "arguments": {}
    }
]