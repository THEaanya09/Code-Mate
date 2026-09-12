import os

import ollama

from config import MODEL, MAX_AGENT_STEPS
from prompts import SYSTEM_PROMPT
from executor import (
    parse_tool_calls,
    execute_tool
)


OLLAMA_HOST = os.getenv(
    "OLLAMA_HOST",
    "http://localhost:11434"
)


ollama_client = ollama.Client(
    host=OLLAMA_HOST
)


VALID_TOOLS = {
    "list_files",
    "read_file",
    "write_file",
    "run_command",
    "git_status",
    "git_diff"
}


def was_tool_already_used(
    tool_call,
    tool_history
):

    tool_name = tool_call.get(
        "name"
    )

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


def get_previous_tool_result(
    tool_call,
    tool_history
):

    tool_name = tool_call.get(
        "name"
    )

    arguments = tool_call.get(
        "arguments",
        {}
    )

    for item in reversed(
        tool_history
    ):

        if (
            item["tool"] == tool_name
            and item["arguments"] == arguments
        ):

            return item["result"]

    return None


def clean_final_answer(
    content,
    tool_history
):

    """
    Clean weak model final answers.

    If the model says only:
        The task is complete.

    use the latest successful tool result.
    """

    answer = (
        content
        .replace(
            "Final answer:",
            ""
        )
        .strip()
    )

    weak_answers = {
        "the task is complete.",
        "the task is complete",
        "task complete.",
        "task complete"
    }

    if answer.lower() in weak_answers:

        if tool_history:

            latest = tool_history[-1]

            result = str(
                latest["result"]
            )

            if not result.startswith(
                "ERROR"
            ):

                return result

    return answer


def run_agent(
    user_input
):

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

    previous_tool_calls = []

    for step in range(
        MAX_AGENT_STEPS
    ):

        print(
            f"\n--- Agent step {step + 1} ---"
        )

        # ====================================
        # LLM
        # ====================================

        response = ollama_client.chat(
            model=MODEL,
            messages=messages
        )

        content = (
            response.message.content.strip()
        )

        print("\nLLM:")
        print(content)

        # ====================================
        # Parse
        # ====================================

        tool_calls = parse_tool_calls(
            content
        )

        # ====================================
        # Final Answer
        # ====================================

        if not tool_calls:

            final_answer = clean_final_answer(
                content,
                tool_history
            )

            print(
                "\nFinal answer:"
            )

            print(
                final_answer
            )

            return final_answer

        # ====================================
        # Execute ALL detected tool calls
        # ====================================

        executed_any = False

        for tool_call in tool_calls:

            tool_name = tool_call.get(
                "name"
            )

            arguments = tool_call.get(
                "arguments",
                {}
            )

            # ====================================
            # Unknown Tool
            # ====================================

            if tool_name not in VALID_TOOLS:

                print(
                    "\nUnknown tool:",
                    tool_name
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
                            f"""
The tool '{tool_name}' does not exist.

ONLY use these valid tools:

list_files
read_file
write_file
run_command
git_status
git_diff

Do not invent tools.

If the user's request cannot be completed
with the available tools, provide a final
answer explaining why.

Otherwise use valid tools only.
"""
                        )
                    }
                )

                continue

            # ====================================
            # Duplicate Successful Tool
            # ====================================

            if was_tool_already_used(
                tool_call,
                tool_history
            ):

                previous_result = (
                    get_previous_tool_result(
                        tool_call,
                        tool_history
                    )
                )

                print(
                    "\nTool already executed "
                    "successfully."
                )

                print(
                    previous_result
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
                            f"""
This exact tool call was already executed
successfully.

Tool:
{tool_name}

Arguments:
{arguments}

Previous result:
{previous_result}

Do NOT repeat this tool call.

Use the existing result if it is enough
to complete the original request.

If the task is complete, provide the
final answer now.

If another tool is genuinely necessary,
use a different valid tool.
"""
                        )
                    }
                )

                continue

            # ====================================
            # Immediate Duplicate
            # ====================================

            if tool_call in previous_tool_calls:

                print(
                    "\nRepeated tool call detected."
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
                            """
You already called that exact tool.

Do NOT repeat it.

Use the existing result if it is enough
to answer the user.

Otherwise choose a different valid tool.

If the task is complete, provide the
final answer now.
"""
                        )
                    }
                )

                continue

            previous_tool_calls.append(
                tool_call
            )

            # ====================================
            # Execute
            # ====================================

            tool_name, result = execute_tool(
                tool_call
            )

            executed_any = True

            print(
                "\nExecuting tool:",
                tool_name
            )

            print(
                "Arguments:",
                arguments
            )

            print(
                "\nTool result:"
            )

            print(
                result
            )

            # ====================================
            # History
            # ====================================

            tool_history.append(
                {
                    "tool": tool_name,
                    "arguments": arguments,
                    "result": result
                }
            )

            # ====================================
            # Conversation update
            # ====================================

            messages.append(
                {
                    "role": "assistant",
                    "content": content
                }
            )

            status = (
                "ERROR"
                if str(result).startswith(
                    "ERROR"
                )
                else "SUCCESS"
            )

            messages.append(
                {
                    "role": "user",
                    "content": (
                        f"""
TOOL OBSERVATION

Original user request:

{user_input}

Tool:

{tool_name}

Arguments:

{arguments}

Status:

{status}

Result:

{result}

IMPORTANT:

The tool has already been executed.

DO NOT pretend that you executed it.

DO NOT repeat the same successful tool call.

If this result already answers the original
request, provide the final answer immediately.

The final answer MUST contain the actual
useful result.

Do NOT say only:

"The task is complete."

If another tool is genuinely necessary to
complete the original request, use exactly
ONE different valid tool call.
"""
                    )
                }
            )

        # ====================================
        # Multiple tool calls were executed
        # ====================================

        if executed_any:

            continue

    # ========================================
    # Max Steps
    # ========================================

    final_answer = (
        "Agent stopped because the maximum "
        "number of steps was reached."
    )

    print(
        "\nFinal answer:"
    )

    print(
        final_answer
    )

    return final_answer