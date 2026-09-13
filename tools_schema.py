TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": (
                "List files and directories inside the "
                "CodeMate workspace. Optionally provide "
                "a relative directory path."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": (
                            "Optional relative directory path "
                            "inside the workspace. Use an empty "
                            "string for the workspace root."
                        )
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": (
                "Read the contents of a file inside "
                "the CodeMate workspace."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": (
                            "Relative path of the file "
                            "inside the workspace."
                        )
                    }
                },
                "required": [
                    "file_path"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write or replace the contents of a file "
                "inside the CodeMate workspace."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": (
                            "Relative path of the file "
                            "inside the workspace."
                        )
                    },
                    "content": {
                        "type": "string",
                        "description": (
                            "Complete new file contents."
                        )
                    }
                },
                "required": [
                    "file_path",
                    "content"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": (
                "Run an allowed command in the "
                "CodeMate workspace."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": (
                            "Command to execute."
                        )
                    }
                },
                "required": [
                    "command"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": (
                "Get the current Git status of the "
                "project containing the CodeMate workspace. "
                "The workspace argument must be 'current'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace": {
                        "type": "string",
                        "enum": [
                            "current"
                        ],
                        "description": (
                            "The active CodeMate workspace. "
                            "Always use 'current'."
                        )
                    }
                },
                "required": [
                    "workspace"
                ]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "git_diff",
            "description": (
                "Get the current Git diff for the "
                "CodeMate workspace. "
                "The workspace argument must be 'current'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "workspace": {
                        "type": "string",
                        "enum": [
                            "current"
                        ],
                        "description": (
                            "The active CodeMate workspace. "
                            "Always use 'current'."
                        )
                    }
                },
                "required": [
                    "workspace"
                ]
            }
        }
    }
]