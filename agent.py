import json
import os

import ollama

from executor import parse_tool_calls, execute_tool
from prompts import SYSTEM_PROMPT


MODEL = "qwen2.5-coder:3b"
OLLAMA_HOST = os.getenv(
    "OLLAMA_HOST",
    "http://localhost:11434"
)

ollama_client = ollama.Client(host=OLLAMA_HOST)

VALID_TOOLS = {
    "list_files",
    "read_file",
    "write_file",
    "run_command",
    "git_status",
    "git_diff"
}

MAX_STEPS = 12


def was_tool_already_used(history, tool_name, arguments):
    for item in history:
        if (
            item.get("name") == tool_name
            and item.get("arguments") == arguments
        ):
            return True
    return False


def get_previous_tool_result(history, tool_name):
    for item in reversed(history):
        if item.get("name") == tool_name:
            return item.get("result")
    return None


def clean_final_answer(response):
    if not response:
        return "Task completed."

    response = response.strip()

    # Remove accidental JSON wrapping if the model returns it.
    try:
        obj = json.loads(response)

        if isinstance(obj, dict):
            if "response" in obj:
                return str(obj["response"]).strip()

            if "answer" in obj:
                return str(obj["answer"]).strip()
    except Exception:
        pass

    return response


def call_llm(messages):
    response = ollama_client.chat(
        model=MODEL,
        messages=messages,
        options={
            "temperature": 0.1
        }
    )

    return response["message"]["content"]


def build_grounded_summary(user_request, tool_history):
    successful = []
    failed = []

    for item in tool_history:
        result = str(item.get("result", ""))

        if result.startswith("ERROR:"):
            failed.append(item)
        else:
            successful.append(item)

    evidence = []

    for item in tool_history:
        evidence.append(
            "TOOL: "
            + str(item.get("name"))
            + "\nARGUMENTS: "
            + json.dumps(
                item.get("arguments", {}),
                ensure_ascii=False
            )
            + "\nRESULT:\n"
            + str(item.get("result", ""))
        )

    evidence_text = "\n\n---\n\n".join(evidence)

    summary_prompt = f"""
You are the final response writer for CodeMate.

The user requested:

{user_request}

Below are the ACTUAL tool calls and their ACTUAL results.

You MUST use only this evidence.

Do NOT invent:
- outputs
- errors
- file changes
- filenames
- test results
- numbers
- successful execution

If the evidence shows an error, say there was an error.

If the evidence shows a successful verification, report that exact result.

If a file was modified, mention the exact filename only if shown
in the tool evidence.

If the final verification output is available, use that output.

Do not claim that an error occurred unless the tool result actually
contains that error.

Do not claim that a script produced a particular number unless the
tool result actually contains that number.

Return a concise factual answer with:

1. What was changed, if anything.
2. What was verified.
3. The actual final result.

ACTUAL TOOL EVIDENCE:

{evidence_text}
"""

    try:
        response = ollama_client.chat(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": summary_prompt
                }
            ],
            options={
                "temperature": 0.0
            }
        )

        return clean_final_answer(
            response["message"]["content"]
        )

    except Exception:
        # Safe deterministic fallback.
        if tool_history:
            last = tool_history[-1]

            return (
                "The task reached its final tool result.\n\n"
                "Last tool: "
                + str(last.get("name"))
                + "\n"
                "Result:\n"
                + str(last.get("result", ""))
            )

        return "The task could not be completed."


def run_agent(user_request):
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": user_request
        }
    ]

    tool_history = []

    for step in range(1, MAX_STEPS + 1):

        print(f"\n--- Agent step {step} ---")

        try:
            response = call_llm(messages)
        except Exception as e:
            return (
                "CodeMate could not contact the LLM.\n\n"
                f"Error: {e}"
            )

        print("LLM:")
        print(response)

        tool_calls = parse_tool_calls(response)

        # No tool call means the model believes it has enough
        # information. Generate a grounded final response instead
        # of trusting its free-form summary.
        if not tool_calls:
            if tool_history:
                final_answer = build_grounded_summary(
                    user_request,
                    tool_history
                )
                print("Final grounded response:")
                print(final_answer)
                return final_answer

            return clean_final_answer(response)

        executed_any = False

        for tool_call in tool_calls:

            tool_name = tool_call.get("name")
            arguments = tool_call.get(
                "arguments",
                {}
            )

            if tool_name not in VALID_TOOLS:
                print(
                    "Invalid tool blocked:",
                    tool_name
                )

                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "ERROR: Invalid tool.\n"
                            f"'{tool_name}' is not available.\n"
                            "Use only the six tools listed "
                            "in the system prompt."
                        )
                    }
                )

                continue

            if was_tool_already_used(
                tool_history,
                tool_name,
                arguments
            ):
                print(
                    "Repeated tool call blocked:",
                    tool_name
                )

                messages.append(
                    {
                        "role": "user",
                        "content": (
                            "ERROR: You already executed this "
                            "exact tool call successfully or "
                            "attempted it already.\n\n"
                            "Do NOT repeat it.\n"
                            "Use the previous result and "
                            "choose a different next action, "
                            "or provide the final answer."
                        )
                    }
                )

                continue

            print("Executing tool:", tool_name)
            print("Arguments:", arguments)

            result = execute_tool(
                tool_name,
                arguments
            )

            print("Tool result:")
            print(result)

            history_item = {
                "name": tool_name,
                "arguments": arguments,
                "result": result
            }

            tool_history.append(history_item)
            executed_any = True

            if str(result).startswith("ERROR:"):
                observation = (
                    "The previous tool execution FAILED.\n\n"
                    "You MUST use this actual error to decide "
                    "the next action.\n"
                    "Do NOT claim the task is complete.\n\n"
                    "TOOL RESULT:\n"
                    + str(result)
                )
            else:
                observation = (
                    "The previous tool execution succeeded.\n\n"
                    "Use THIS result as the source of truth.\n"
                    "Do not invent a different result.\n\n"
                    "TOOL RESULT:\n"
                    + str(result)
                )

                if tool_name == "write_file":
                    observation += (
                        "\n\nThe file was modified successfully. "
                        "Do NOT repeat the same write_file call. "
                        "Verify the change by reading the file or "
                        "running the relevant command."
                    )

                if tool_name == "run_command":
                    observation += (
                        "\n\nThis is fresh command output. "
                        "Base your next decision on this output."
                    )

            messages.append(
                {
                    "role": "assistant",
                    "content": response
                }
            )

            messages.append(
                {
                    "role": "user",
                    "content": observation
                }
            )

        if not executed_any:
            # The model attempted only duplicate/invalid calls.
            # Force it to reason from the evidence already collected.
            messages.append(
                {
                    "role": "user",
                    "content": (
                        "No new tool was executed in this step.\n\n"
                        "Stop repeating previous tool calls.\n"
                        "Review the existing tool results and either "
                        "choose a genuinely new action or provide "
                        "the final answer."
                    )
                }
            )

    # Maximum steps reached.
    # Do not let the model invent a success message.
    if tool_history:
        return build_grounded_summary(
            user_request,
            tool_history
        )

    return "CodeMate reached its maximum number of steps."


if __name__ == "__main__":
    print(
        run_agent(
            "Run buggy_test.py and fix it if necessary."
        )
    )
