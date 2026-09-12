import json
import os

from dotenv import load_dotenv
from groq import Groq

from executor import execute_tool
from prompts import SYSTEM_PROMPT
from tools_schema import TOOLS_SCHEMA


load_dotenv()


MODEL = os.getenv(
    "GROQ_MODEL",
    "openai/gpt-oss-20b"
)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise RuntimeError(
        "GROQ_API_KEY is not configured."
    )


groq_client = Groq(
    api_key=GROQ_API_KEY
)


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
    for index in range(len(history) - 1, -1, -1):

        item = history[index]

        if (
            item.get("name") == tool_name
            and item.get("arguments") == arguments
        ):

            # If a file was written after the previous call,
            # allow the same call again for fresh verification.
            for later_item in history[index + 1:]:
                if later_item.get("name") == "write_file":
                    return False

            return True

    return False


def clean_final_answer(response):
    if not response:
        return "Task completed."

    response = response.strip()

    try:
        obj = json.loads(response)

        if isinstance(obj, dict):

            if "response" in obj:
                return str(
                    obj["response"]
                ).strip()

            if "answer" in obj:
                return str(
                    obj["answer"]
                ).strip()

    except Exception:
        pass

    return response


def call_llm(messages):
    response = groq_client.chat.completions.create(
        model=MODEL,
        messages=messages,
        tools=TOOLS_SCHEMA,
        tool_choice="auto",
        temperature=0.1,
    )

    return response.choices[0].message


def build_grounded_summary(
    user_request,
    tool_history
):
    evidence = []

    for item in tool_history:

        evidence.append(
            "TOOL: "
            + str(item.get("name"))
            + "\nARGUMENTS: "
            + json.dumps(
                item.get(
                    "arguments",
                    {}
                ),
                ensure_ascii=False
            )
            + "\nRESULT:\n"
            + str(
                item.get(
                    "result",
                    ""
                )
            )
        )

    evidence_text = (
        "\n\n---\n\n".join(evidence)
    )

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

If the evidence shows an error,
say there was an error.

If the evidence shows successful
verification, report the exact result.

If a file was modified, mention the
exact filename shown in the evidence.

Return a concise factual answer with:

1. What was changed.
2. What was verified.
3. The actual final result.

ACTUAL TOOL EVIDENCE:

{evidence_text}
"""

    try:

        response = groq_client.chat.completions.create(
            model=MODEL,
            messages=[
                {
                    "role": "system",
                    "content": summary_prompt
                }
            ],
            temperature=0.0
        )

        return clean_final_answer(
            response.choices[0].message.content
            or ""
        )

    except Exception:

        if tool_history:

            last = tool_history[-1]

            return (
                "The task reached its final "
                "tool result.\n\n"
                "Last tool: "
                + str(last.get("name"))
                + "\n"
                "Result:\n"
                + str(
                    last.get(
                        "result",
                        ""
                    )
                )
            )

        return (
            "The task could not be completed."
        )


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

    for step in range(
        1,
        MAX_STEPS + 1
    ):

        print(
            f"\n--- Agent step {step} ---"
        )

        try:

            message = call_llm(
                messages
            )

        except Exception as e:

            return (
                "CodeMate could not contact "
                "the LLM.\n\n"
                f"Error: {e}"
            )

        content = (
            message.content
            or ""
        )

        print("LLM:")
        print(content)

        tool_calls = (
            message.tool_calls
            or []
        )

        # -------------------------------------------------
        # NO TOOL CALL
        # -------------------------------------------------

        if not tool_calls:

            if tool_history:

                final_answer = (
                    build_grounded_summary(
                        user_request,
                        tool_history
                    )
                )

                print(
                    "Final grounded response:"
                )

                print(final_answer)

                return final_answer

            return clean_final_answer(
                content
            )

        # -------------------------------------------------
        # ASSISTANT MESSAGE WITH TOOL CALLS
        # -------------------------------------------------

        messages.append(message)

        executed_any = False

        for tool_call in tool_calls:

            tool_name = (
                tool_call.function.name
            )

            raw_arguments = (
                tool_call.function.arguments
                or "{}"
            )

            try:

                arguments = json.loads(
                    raw_arguments
                )

            except json.JSONDecodeError:

                result = (
                    "ERROR: Invalid JSON "
                    "arguments from model."
                )

                print(result)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id":
                            tool_call.id,
                        "name":
                            tool_name,
                        "content":
                            result
                    }
                )

                continue

            print(
                "Tool requested:",
                tool_name
            )

            print(
                "Arguments:",
                arguments
            )

            # -------------------------------------------------
            # VALIDATE TOOL
            # -------------------------------------------------

            if tool_name not in VALID_TOOLS:

                result = (
                    "ERROR: Unknown tool "
                    f"'{tool_name}'."
                )

                print(result)

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id":
                            tool_call.id,
                        "name":
                            tool_name,
                        "content":
                            result
                    }
                )

                continue

            # -------------------------------------------------
            # DUPLICATE PROTECTION
            # -------------------------------------------------

            if was_tool_already_used(
                tool_history,
                tool_name,
                arguments
            ):

                result = (
                    "ERROR: This exact tool "
                    "call was already attempted. "
                    "Use the previous result or "
                    "choose a different action."
                )

                print(
                    "Repeated tool call blocked:",
                    tool_name
                )

                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id":
                            tool_call.id,
                        "name":
                            tool_name,
                        "content":
                            result
                    }
                )

                continue

            # -------------------------------------------------
            # EXECUTE
            # -------------------------------------------------

            print(
                "Executing tool:",
                tool_name
            )

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

            tool_history.append(
                history_item
            )

            executed_any = True

            # -------------------------------------------------
            # SEND TOOL RESULT BACK TO MODEL
            # -------------------------------------------------

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id":
                        tool_call.id,
                    "name":
                        tool_name,
                    "content":
                        str(result)
                }
            )

        # -------------------------------------------------
        # NOTHING NEW WAS EXECUTED
        # -------------------------------------------------

        if not executed_any:

            messages.append(
                {
                    "role": "user",
                    "content": (
                        "No new tool was executed "
                        "in this step.\n\n"
                        "Review the existing tool "
                        "results and either choose "
                        "a genuinely new action or "
                        "provide the final answer."
                    )
                }
            )

    # -----------------------------------------------------
    # MAX STEPS
    # -----------------------------------------------------

    if tool_history:

        return build_grounded_summary(
            user_request,
            tool_history
        )

    return (
        "CodeMate reached its maximum "
        "number of steps."
    )


if __name__ == "__main__":

    print(
        run_agent(
            "Run buggy_test.py and fix it "
            "if necessary."
        )
    )