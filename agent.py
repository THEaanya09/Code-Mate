import ollama

from config import MODEL, MAX_AGENT_STEPS
from prompts import SYSTEM_PROMPT
from executor import (
    parse_tool_calls,
    execute_tool
)


def was_tool_already_used(
    tool_call,
    tool_history
):

    tool_name = tool_call.get("name")

    arguments = tool_call.get(
        "arguments",
        {}
    )

    for item in tool_history:

        if (
            item["tool"] == tool_name
            and item["arguments"] == arguments
            and not str(
                item["result"]
            ).startswith("ERROR")
        ):

            return True

    return False


def run_agent(user_input):

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },

        {
            "role": "user",
            "content": user_input
        }
    ]

    tool_history = []

    previous_tool_call = None

    for step in range(MAX_AGENT_STEPS):

        print(
            f"\n--- Agent step {step + 1} ---"
        )

        response = ollama.chat(
            model=MODEL,
            messages=messages
        )

        content = (
            response.message.content.strip()
        )

        print("\nLLM:")
        print(content)

        tool_calls = parse_tool_calls(
            content
        )

        # --------------------------------
        # No tool call = final answer
        # --------------------------------

        if not tool_calls:

            final_answer = (
                content
                .replace(
                    "Final answer:",
                    ""
                )
                .strip()
            )

            print("\nFinal answer:")
            print(final_answer)

            return

        tool_call = tool_calls[0]

        # --------------------------------
        # Detect repeated successful tool
        # --------------------------------

        if was_tool_already_used(
            tool_call,
            tool_history
        ):

            print(
                "\nTool already executed "
                "successfully."
            )

            for item in reversed(tool_history):

                if (
                    item["tool"]
                    == tool_call["name"]
                    and item["arguments"]
                    == tool_call.get(
                        "arguments",
                        {}
                    )
                ):

                    print("\nFinal answer:")
                    print(item["result"])

                    return

        # --------------------------------
        # Detect immediate duplicate
        # --------------------------------

        if tool_call == previous_tool_call:

            print(
                "\nAgent tried to repeat "
                "the same tool call."
            )

            messages.append(
                {
                    "role": "assistant",
                    "content": content
                }
            )

            messages.append(
                {
                    "role": "user",
                    "content": (
                        "You already executed this "
                        "exact tool call.\n\n"
                        "Do not call any tool again.\n"
                        "Provide the final answer now."
                    )
                }
            )

            previous_tool_call = None

            continue

        previous_tool_call = tool_call

        # --------------------------------
        # Get arguments
        # --------------------------------

        arguments = tool_call.get(
            "arguments",
            {}
        )

        # --------------------------------
        # Execute tool
        # --------------------------------

        tool_name, result = execute_tool(
            tool_call
        )

        print(
            "\nExecuting tool:",
            tool_name
        )

        print(
            "Arguments:",
            arguments
        )

        print("\nTool result:")
        print(result)

        # --------------------------------
        # Save history
        # --------------------------------

        tool_history.append(
            {
                "tool": tool_name,
                "arguments": arguments,
                "result": result
            }
        )

        print("\nTool history:")
        print(tool_history)

        # --------------------------------
        # Simple file listing request
        # --------------------------------

        if tool_name == "list_files":

            print("\nFinal answer:")
            print(result)

            return

        # --------------------------------
        # Add assistant response
        # --------------------------------

        messages.append(
            {
                "role": "assistant",
                "content": content
            }
        )

        status = (
            "ERROR"
            if str(result).startswith("ERROR")
            else "SUCCESS"
        )

        # --------------------------------
        # Add tool observation
        # --------------------------------

        messages.append(
            {
                "role": "user",
                "content": (
                    f"""
TOOL OBSERVATION

Original user request:
{user_input}

Tool executed:
{tool_name}

Status:
{status}

Result:
{result}

Tool history:
{tool_history}


DECIDE THE NEXT ACTION CAREFULLY.

- Do exactly what the user asked.
- Do not invent extra tasks.
- Do not repeat a successful tool call.
- If the tool result already answers the
  user's request, provide the final answer now.
- If the original request is complete, provide
  the final answer immediately.
- Do not call the same successful tool again.
- Use another tool only if it is genuinely
  necessary to complete the original request.
- Include the actual useful result in the
  final answer.
- Do not answer only with "The task is complete."
- Do not repeat these instructions.
- Use exactly ONE tool call if another tool
  is necessary.
"""
                )
            }
        )

    print("\nFinal answer:")

    print(
        "Agent stopped because the maximum "
        "number of steps was reached."
    )