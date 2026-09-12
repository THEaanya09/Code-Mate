import json
import re

from tools import TOOLS


def _extract_json_objects(text):
    """
    Extract multiple JSON objects from arbitrary LLM text.

    Handles cases like:
    {
        "name": "write_file",
        "arguments": {...}
    }

    {
        "name": "run_command",
        "arguments": {...}
    }
    """

    objects = []

    decoder = json.JSONDecoder()
    index = 0

    while index < len(text):

        start = text.find("{", index)

        if start == -1:
            break

        try:

            obj, end = decoder.raw_decode(
                text[start:]
            )

            if isinstance(obj, dict):
                objects.append(obj)

            index = start + end

        except json.JSONDecodeError:

            index = start + 1

    return objects


def _normalize_tool_call(obj):
    """
    Convert a JSON object into our standard tool-call format.
    """

    if not isinstance(obj, dict):
        return None

    name = obj.get("name")

    arguments = obj.get(
        "arguments",
        {}
    )

    if not name:
        return None

    if not isinstance(arguments, dict):
        return None

    return {
        "name": name,
        "arguments": arguments
    }


def parse_tool_calls(text):
    """
    Parse one or multiple tool calls from LLM output.

    Supported formats:

    1. Standard JSON
    2. Markdown JSON
    3. Multiple JSON objects
    4. Simple text tool call
    """

    if not text:
        return []

    text = text.strip()

    tool_calls = []

    # ---------------------------------------------------------
    # 1. Extract all JSON objects from the response
    # ---------------------------------------------------------

    json_objects = _extract_json_objects(
        text
    )

    for obj in json_objects:

        tool_call = _normalize_tool_call(
            obj
        )

        if tool_call:
            tool_calls.append(
                tool_call
            )

    if tool_calls:
        return tool_calls

    # ---------------------------------------------------------
    # 2. Fallback: simple text format
    #
    # run_command
    # -> command: "python hello.py"
    # ---------------------------------------------------------

    name_match = re.search(
        r"\b(list_files|read_file|write_file|run_command|git_status|git_diff)\b",
        text,
        re.IGNORECASE
    )

    if not name_match:
        return []

    name = name_match.group(1)

    arguments = {}

    if name == "run_command":

        match = re.search(
            r'command\s*:\s*"([^"]*)"',
            text,
            re.IGNORECASE
        )

        if match:
            arguments = {
                "command": match.group(1)
            }

    elif name in {
        "read_file",
        "write_file"
    }:

        match = re.search(
            r'file_path\s*:\s*"([^"]*)"',
            text,
            re.IGNORECASE
        )

        if match:

            arguments["file_path"] = (
                match.group(1)
            )

    if arguments:
        return [
            {
                "name": name,
                "arguments": arguments
            }
        ]

    return []


def execute_tool(
    tool_call
):
    """
    Execute one tool call safely through the
    registered TOOLS dictionary.
    """

    if not isinstance(
        tool_call,
        dict
    ):
        return (
            None,
            "Invalid tool call."
        )

    tool_name = tool_call.get(
        "name"
    )

    arguments = tool_call.get(
        "arguments",
        {}
    )

    if tool_name not in TOOLS:

        return (
            tool_name,
            f"Unknown tool: {tool_name}"
        )

    if not isinstance(
        arguments,
        dict
    ):

        return (
            tool_name,
            "Tool arguments must be a JSON object."
        )

    try:

        print(
            f"Executing tool: {tool_name}"
        )

        print(
            f"Arguments: {arguments}"
        )

        result = TOOLS[tool_name](
            **arguments
        )

        return (
            tool_name,
            result
        )

    except TypeError as error:

        return (
            tool_name,
            f"Invalid arguments for {tool_name}: {error}"
        )

    except Exception as error:

        return (
            tool_name,
            f"Tool execution failed: {error}"
        )


def execute_tool_calls(
    tool_calls
):
    """
    Execute multiple tool calls sequentially.

    Returns a list of:

    {
        "name": "...",
        "result": "..."
    }
    """

    results = []

    for tool_call in tool_calls:

        tool_name, result = execute_tool(
            tool_call
        )

        results.append(
            {
                "name": tool_name,
                "result": result
            }
        )

    return results