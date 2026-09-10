import json

from tools import TOOLS
from tools_schema import TOOLS_SCHEMA


def is_valid_tool_call(tool_call):

    if not isinstance(tool_call, dict):
        return False

    if "name" not in tool_call:
        return False

    if "arguments" not in tool_call:
        return False

    tool_names = {
        tool["name"]
        for tool in TOOLS_SCHEMA
    }

    if tool_call["name"] not in tool_names:
        return False

    if not isinstance(
        tool_call["arguments"],
        dict
    ):
        return False

    return True


def parse_tool_calls(content):

    content = content.strip()

    # Remove Markdown fences
    content = content.replace(
        "```json",
        ""
    )

    content = content.replace(
        "```",
        ""
    )

    content = content.strip()

    decoder = json.JSONDecoder()

    tool_calls = []

    index = 0

    while index < len(content):

        if content[index] != "{":

            index += 1
            continue

        try:

            obj, consumed = decoder.raw_decode(
                content[index:]
            )

            if is_valid_tool_call(obj):

                tool_calls.append(obj)

            index += consumed

        except json.JSONDecodeError:

            index += 1

    return tool_calls


def parse_tool_call(content):

    tool_calls = parse_tool_calls(content)

    if not tool_calls:
        return None

    return tool_calls[0]


def execute_tool(tool_call):

    if not tool_call:

        return None, "Not a tool call."

    if not is_valid_tool_call(tool_call):

        return None, "Invalid tool call."

    tool_name = tool_call["name"]

    arguments = tool_call["arguments"]

    # Normalize nested argument values
    for key, value in arguments.items():

        if (
            isinstance(value, dict)
            and "value" in value
        ):

            arguments[key] = value["value"]

    tool = TOOLS.get(tool_name)

    if not tool:

        return tool_name, (
            f"ERROR: Unknown tool '{tool_name}'"
        )

    try:

        result = tool(**arguments)

    except Exception as e:

        result = f"ERROR: {str(e)}"

    return tool_name, result