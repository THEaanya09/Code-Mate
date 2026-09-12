import ast
import json
import os

from groq import Groq

from config import get_api_key, get_model
from executor import execute_tool
from prompts import SYSTEM_PROMPT
from tools_schema import TOOLS_SCHEMA


VALID_TOOLS = {
    "list_files",
    "read_file",
    "write_file",
    "run_command",
    "git_status",
    "git_diff",
}

MAX_STEPS = 12


def get_client():
    api_key = get_api_key()

    if not api_key:
        raise RuntimeError(
            "GROQ_API_KEY is not configured. "
            "Run CodeMate from the CLI to configure it."
        )

    return Groq(api_key=api_key)


def was_tool_already_used(history, tool_name, arguments):
    for item in history:
        if (
            item.get("name") == tool_name
            and item.get("arguments") == arguments
        ):
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
                return str(obj["response"]).strip()

            if "answer" in obj:
                return str(obj["answer"]).strip()

    except Exception:
        pass

    return response


def call_llm(client, messages):
    response = client.chat.completions.create(
        model=get_model(),
        messages=messages,
        tools=TOOLS_SCHEMA,
        tool_choice="auto",
        temperature=0.1,
    )

    return response.choices[0].message


def get_top_level_test_statements(source):
    """
    Return top-level statements from a Python source file.

    Used to protect test/invocation statements from accidental
    modification during bug fixing.
    """

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    statements = []

    for node in tree.body:
        if isinstance(
            node,
            (
                ast.Expr,
                ast.Assign,
                ast.AnnAssign,
                ast.AugAssign,
                ast.Assert,
                ast.If,
            ),
        ):
            try:
                statements.append(
                    ast.unparse(node)
                )
            except Exception:
                pass

    return statements


def task_requires_test_preservation(user_request):
    request = user_request.lower()

    keywords = [
        "test",
        "tests",
        "test case",
        "testcase",
        "pytest",
        "unittest",
        "without changing the test",
        "without modifying the test",
        "don't change the test",
        "do not change the test",
        "preserve the test",
    ]

    return any(keyword in request for keyword in keywords)


def get_original_file_content(file_path):
    try:
        result = execute_tool(
            "read_file",
            {
                "file_path": file_path
            }
        )

        if isinstance(result, str):
            return result

    except Exception:
        pass

    return None


def validate_test_preservation(
    file_path,
    original_content,
    new_content,
):
    if not original_content:
        return True

    original_statements = get_top_level_test_statements(
        original_content
    )

    new_statements = get_top_level_test_statements(
        new_content
    )

    if not original_statements:
        return True

    original_set = set(original_statements)
    new_set = set(new_statements)

    missing = original_set - new_set

    return not missing


def build_grounded_summary(
    client,
    user_request,
    tool_history,
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
        response = client.chat.completions.create(
            model=get_model(),
            messages=[
                {
                    "role": "system",
                    "content": summary_prompt,
                }
            ],
            temperature=0.0,
        )

        return clean_final_answer(
            response.choices[0].message.content
            or ""
        )

    except Exception:
        if tool_history:
            last = tool_history[-1]

            return (
                "The task reached its final tool result.\n\n"
                f"Last tool: {last.get('name')}\n"
                f"Result:\n{last.get('result', '')}"
            )

        return "No tool execution was completed."


def run_agent(user_message):
    client = get_client()

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_message,
        },
    ]

    tool_history = []

    original_files = {}

    preserve_tests = task_requires_test_preservation(
        user_message
    )

    for step in range(1, MAX_STEPS + 1):
        response = call_llm(
            client,
            messages
        )

        tool_calls = response.tool_calls

        if not tool_calls:
            final_response = (
                response.content
                or ""
            )

            if tool_history:
                return build_grounded_summary(
                    client,
                    user_message,
                    tool_history,
                )

            return clean_final_answer(
                final_response
            )

        assistant_message = {
            "role": "assistant",
            "content": response.content or "",
            "tool_calls": [],
        }

        for tool_call in tool_calls:
            assistant_message["tool_calls"].append(
                {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
            )

        messages.append(assistant_message)

        for tool_call in tool_calls:
            tool_name = tool_call.function.name

            try:
                arguments = json.loads(
                    tool_call.function.arguments
                )
            except json.JSONDecodeError:
                arguments = {}

            if tool_name not in VALID_TOOLS:
                result = (
                    f"ERROR: Invalid tool '{tool_name}'. "
                    f"Allowed tools: "
                    f"{', '.join(sorted(VALID_TOOLS))}"
                )

            elif was_tool_already_used(
                tool_history,
                tool_name,
                arguments,
            ):
                result = (
                    "ERROR: Repeated tool call detected. "
                    "Do not repeat the exact same successful "
                    "tool call. Use the previous result and "
                    "take a different action."
                )

            else:
                if (
                    preserve_tests
                    and tool_name == "write_file"
                ):
                    file_path = arguments.get(
                        "file_path"
                    )

                    new_content = arguments.get(
                        "content"
                    )

                    if file_path and new_content is not None:
                        if file_path not in original_files:
                            original_files[file_path] = (
                                get_original_file_content(
                                    file_path
                                )
                            )

                        original_content = (
                            original_files[file_path]
                        )

                        if not validate_test_preservation(
                            file_path,
                            original_content,
                            new_content,
                        ):
                            result = (
                                "ERROR: Test preservation "
                                "guard blocked this write.\n\n"
                                f"The file '{file_path}' "
                                "contains existing top-level "
                                "test/invocation statements "
                                "that must be preserved.\n\n"
                                "Modify the underlying "
                                "implementation instead of "
                                "changing or removing the "
                                "test scenario."
                            )

                            messages.append(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "content": result,
                                }
                            )

                            tool_history.append(
                                {
                                    "name": tool_name,
                                    "arguments": arguments,
                                    "result": result,
                                }
                            )

                            continue

                print(
                    f"  Step {step}  →  {tool_name}"
                )

                try:
                    result = execute_tool(
                        tool_name,
                        arguments,
                    )
                except Exception as error:
                    result = (
                        f"ERROR executing {tool_name}: "
                        f"{error}"
                    )

            tool_history.append(
                {
                    "name": tool_name,
                    "arguments": arguments,
                    "result": result,
                }
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result),
                }
            )

            if tool_name == "write_file":
                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "IMPORTANT:\n"
                            "A file was modified.\n"
                            "You MUST verify the change "
                            "using an appropriate command "
                            "or inspection tool before "
                            "claiming success."
                        ),
                    }
                )

            if (
                isinstance(result, str)
                and result.startswith("ERROR")
            ):
                messages.append(
                    {
                        "role": "system",
                        "content": (
                            "IMPORTANT:\n"
                            "The previous tool execution "
                            "FAILED.\n"
                            "Do NOT claim the task is complete.\n"
                            "Inspect the error carefully.\n"
                            "If the error can be fixed with "
                            "the available tools, take the "
                            "next necessary action."
                        ),
                    }
                )

    return (
        "Agent stopped because the maximum number "
        "of steps was reached."
    )