import json

from tools import TOOLS


def _extract_json_objects(text):

    objects = []

    decoder = json.JSONDecoder()

    index = 0

    while index < len(text):

        try:

            start = text.find(
                "{",
                index
            )

            if start == -1:
                break

            obj, end = decoder.raw_decode(
                text[start:]
            )

            objects.append(obj)

            index = start + end

        except json.JSONDecodeError:

            index = start + 1

    return objects


def _normalize_tool_call(
    obj
):

    if not isinstance(
        obj,
        dict
    ):
        return None

    # Standard format:
    # {
    #   "name": "run_command",
    #   "arguments": {...}
    # }

    name = obj.get(
        "name"
    )

    arguments = obj.get(
        "arguments",
        {}
    )

    if not name:
        return None

    if not isinstance(
        arguments,
        dict
    ):
        arguments = {}

    return {
        "name": name,
        "arguments": arguments
    }


def parse_tool_calls(
    response
):

    if not response:
        return []

    response = response.strip()

    calls = []

    # -------------------------------------------------
    # 1. Extract JSON objects
    # -------------------------------------------------

    objects = _extract_json_objects(
        response
    )

    for obj in objects:

        call = _normalize_tool_call(
            obj
        )

        if call:
            calls.append(
                call
            )

    # -------------------------------------------------
    # 2. Simple text format
    #
    # run_command
    # -> command: "python hello.py"
    # -------------------------------------------------

    if not calls:

        lines = [
            line.strip()
            for line in response.splitlines()
            if line.strip()
        ]

        tool_name = None

        for line in lines:

            if line in TOOLS:

                tool_name = line

                break

        if tool_name:

            arguments = {}

            for line in lines:

                if ":" not in line:
                    continue

                key, value = line.split(
                    ":",
                    1
                )

                key = key.strip()
                value = value.strip()

                if (
                    len(value) >= 2
                    and value[0] == '"'
                    and value[-1] == '"'
                ):

                    value = value[1:-1]

                arguments[key] = value

            calls.append(
                {
                    "name": tool_name,
                    "arguments": arguments
                }
            )

    return calls


def execute_tool(
    tool_name,
    arguments=None
):

    if tool_name not in TOOLS:

        return (
            "ERROR: Unknown tool '"
            + str(tool_name)
            + "'."
        )

    if arguments is None:

        arguments = {}

    if not isinstance(
        arguments,
        dict
    ):

        return (
            "ERROR: Tool arguments "
            "must be an object."
        )

    tool = TOOLS[
        tool_name
    ]

    try:

        return tool(
            **arguments
        )

    except TypeError as e:

        return (
            "ERROR: Invalid arguments "
            f"for tool '{tool_name}': {e}"
        )

    except Exception as e:

        return (
            "ERROR while executing "
            f"'{tool_name}': {e}"
        )


def execute_tool_calls(
    tool_calls
):

    results = []

    for tool_call in tool_calls:

        name = tool_call.get(
            "name"
        )

        arguments = tool_call.get(
            "arguments",
            {}
        )

        result = execute_tool(
            name,
            arguments
        )

        results.append(
            {
                "name": name,
                "arguments": arguments,
                "result": result
            }
        )

    return results
