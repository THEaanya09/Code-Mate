import json

from tools import TOOLS


def parse_tool_calls(content):
    """
    Parse one tool call from the LLM response.

    Supported formats:

    1. JSON
    2. Markdown JSON
    3. Simple text format

       run_command
       -> command: "python hello.py"
    """

    content = content.strip()

    if not content:
        return []

    # ========================================
    # Remove markdown code fences
    # ========================================

    cleaned = content

    if cleaned.startswith("```"):

        lines = cleaned.splitlines()

        if lines:
            lines = lines[1:]

        if (
            lines
            and lines[-1].strip() == "```"
        ):
            lines = lines[:-1]

        cleaned = "\n".join(
            lines
        ).strip()

    # ========================================
    # JSON object
    # ========================================

    try:

        data = json.loads(cleaned)

        if (
            isinstance(data, dict)
            and "name" in data
            and "arguments" in data
        ):

            return [data]

    except json.JSONDecodeError:
        pass

    # ========================================
    # JSON embedded inside text
    # ========================================

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start != -1 and end != -1:

        json_part = cleaned[
            start:end + 1
        ]

        try:

            data = json.loads(
                json_part
            )

            if (
                isinstance(data, dict)
                and "name" in data
                and "arguments" in data
            ):

                return [data]

        except json.JSONDecodeError:
            pass

    # ========================================
    # Simple text format
    #
    # run_command
    # -> command: "python hello.py"
    # ========================================

    lines = [
        line.strip()
        for line in cleaned.splitlines()
        if line.strip()
    ]

    if not lines:
        return []

    tool_name = lines[0]

    if tool_name not in TOOLS:
        return []

    arguments = {}

    for line in lines[1:]:

        if "->" in line:

            line = line.replace(
                "->",
                "",
                1
            ).strip()

        if ":" not in line:
            continue

        key, value = line.split(
            ":",
            1
        )

        key = key.strip()
        value = value.strip()

        # Remove quotes
        if (
            len(value) >= 2
            and value[0] == '"'
            and value[-1] == '"'
        ):

            value = value[1:-1]

        elif (
            len(value) >= 2
            and value[0] == "'"
            and value[-1] == "'"
        ):

            value = value[1:-1]

        arguments[key] = value

    return [
        {
            "name": tool_name,
            "arguments": arguments
        }
    ]


def execute_tool(tool_call):
    """
    Execute a parsed tool call.

    Returns:
        (tool_name, result)
    """

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
            (
                f"ERROR: Unknown tool "
                f"'{tool_name}'."
            )
        )

    if not isinstance(
        arguments,
        dict
    ):

        return (
            tool_name,
            (
                "ERROR: Tool arguments "
                "must be an object."
            )
        )

    try:

        result = TOOLS[tool_name](
            **arguments
        )

        return (
            tool_name,
            str(result)
        )

    except TypeError as e:

        return (
            tool_name,
            (
                f"ERROR: Invalid arguments "
                f"for '{tool_name}': {e}"
            )
        )

    except Exception as e:

        return (
            tool_name,
            f"ERROR: {str(e)}"
        )