import ast
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

            for later_item in history[index + 1:]:

                if later_item.get("name") == "write_file":
                    return False

            return True

    return False


def clean_final_answer(response):

    if not response:
        return ""

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
        temperature=0.1
    )

    return response.choices[0].message


def task_requires_test_preservation(user_request):

    text = user_request.lower()

    preservation_phrases = [
        "without changing the test",
        "do not change the test",
        "don't change the test",
        "preserve the test",
        "keep the test unchanged",
        "without modifying the test",
        "do not modify the test",
        "don't modify the test"
    ]

    return any(
        phrase in text
        for phrase in preservation_phrases
    )


def normalize_ast_node(node):

    return ast.dump(
        node,
        annotate_fields=True,
        include_attributes=False
    )


def get_top_level_test_statements(source):

    try:

        tree = ast.parse(source)

    except SyntaxError:

        return None

    statements = []

    for node in tree.body:

        # Function/class definitions are implementation.
        # Everything else at module level is part of the
        # script's test/invocation behavior.
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
                ast.ClassDef
            )
        ):
            continue

        statements.append(
            normalize_ast_node(node)
        )

    return statements


def validate_test_preservation(
    original_content,
    proposed_content
):

    original_statements = get_top_level_test_statements(
        original_content
    )

    proposed_statements = get_top_level_test_statements(
        proposed_content
    )

    if original_statements is None:
        return (
            False,
            "Original file could not be parsed as Python."
        )

    if proposed_statements is None:
        return (
            False,
            "Proposed file could not be parsed as Python."
        )

    if original_statements != proposed_statements:

        return (
            False,
            (
                "TEST PRESERVATION VIOLATION: "
                "The proposed change modifies the existing "
                "top-level test/invocation code. "
                "Keep the original test scenario exactly "
                "unchanged and modify only the underlying "
                "implementation."
            )
        )

    return True, ""


def get_original_file_content(
    tool_history,
    file_path
):

    for item in reversed(tool_history):

        if item.get("name") != "read_file":
            continue

        arguments = item.get(
            "arguments",
            {}
        )

        if arguments.get("file_path") != file_path:
            continue

        result = item.get(
            "result",
            ""
        )

        if (
            isinstance(result, str)
            and not result.startswith("ERROR:")
            and "[File content truncated.]" not in result
        ):
            return result

    return None


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

Below are the ACTUAL tool calls and ACTUAL results.

You MUST use only this evidence.

Do NOT invent:
- outputs
- errors
- file changes
- filenames
- test results
- numbers
- successful execution

IMPORTANT:

If write_file modified a file, report the
exact filename from the tool evidence.

If run_command was executed after write_file,
use that newest run_command result as the
verification result.

If the newest verification succeeded, report
that exact successful result.

If the newest verification failed, clearly
report that the verification failed.

If a test-preservation violation was blocked,
do not claim that the test was modified.

If the evidence does not prove that the task
was completed, do NOT claim that it was completed.

Return a concise response using:

1. What was changed.
2. What was verified.
3. Final result.

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

        answer = clean_final_answer(
            response.choices[0].message.content
            or ""
        )

        if answer:
            return answer

    except Exception:
        pass

    return build_fallback_summary(tool_history)


def build_fallback_summary(tool_history):

    if not tool_history:
        return "No tool actions were completed."

    last_tool = tool_history[-1]

    last_name = str(
        last_tool.get("name")
    )

    last_result = str(
        last_tool.get(
            "result",
            ""
        )
    )

    changed_files = []

    for item in tool_history:

        if item.get("name") == "write_file":

            arguments = item.get(
                "arguments",
                {}
            )

            file_path = arguments.get(
                "file_path"
            )

            if file_path:
                changed_files.append(
                    str(file_path)
                )

    if changed_files:
        changed_text = ", ".join(
            dict.fromkeys(changed_files)
        )
    else:
        changed_text = "None"

    if last_name == "run_command":

        if last_result.startswith("ERROR:"):

            return (
                "1. What was changed: "
                + changed_text
                + ".\n\n"
                "2. What was verified: "
                "The task was re-run after the "
                "file modification.\n\n"
                "3. Final result: Verification failed.\n\n"
                + last_result
            )

        return (
            "1. What was changed: "
            + changed_text
            + ".\n\n"
            "2. What was verified: "
            "The modified code was executed again.\n\n"
            "3. Final result:\n"
            + last_result
        )

    return (
        "1. What was changed: "
        + changed_text
        + ".\n\n"
        "2. What was verified: "
        + last_name
        + " completed successfully.\n\n"
        "3. Final result:\n"
        + last_result
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

    preserve_tests = task_requires_test_preservation(
        user_request
    )

    for step in range(
        1,
        MAX_STEPS + 1
    ):

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

        tool_calls = (
            message.tool_calls
            or []
        )

        # -----------------------------------------
        # NO TOOL CALL
        # -----------------------------------------

        if not tool_calls:

            if tool_history:

                return build_grounded_summary(
                    user_request,
                    tool_history
                )

            answer = clean_final_answer(
                message.content
                or ""
            )

            if answer:
                return answer

            return (
                "CodeMate could not determine "
                "a final result."
            )

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
                f"  Step {step}  →  {tool_name}"
            )

            # -------------------------------------
            # VALIDATE TOOL
            # -------------------------------------

            if tool_name not in VALID_TOOLS:

                result = (
                    "ERROR: Unknown tool "
                    f"'{tool_name}'."
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

            # -------------------------------------
            # DUPLICATE PROTECTION
            # -------------------------------------

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

            # -------------------------------------
            # TEST PRESERVATION GUARD
            # -------------------------------------

            if (
                tool_name == "write_file"
                and preserve_tests
            ):

                file_path = arguments.get(
                    "file_path"
                )

                proposed_content = arguments.get(
                    "content"
                )

                original_content = (
                    get_original_file_content(
                        tool_history,
                        file_path
                    )
                )

                if (
                    original_content is not None
                    and isinstance(
                        proposed_content,
                        str
                    )
                ):

                    safe, reason = (
                        validate_test_preservation(
                            original_content,
                            proposed_content
                        )
                    )

                    if not safe:

                        result = (
                            "ERROR: "
                            + reason
                            + "\n\n"
                            "Do NOT change the test "
                            "or its inputs. Modify only "
                            "the underlying implementation "
                            "and try write_file again."
                        )

                        print(
                            "  ✗ write_file blocked: "
                            "test preservation violation"
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

            # -------------------------------------
            # EXECUTE TOOL
            # -------------------------------------

            result = execute_tool(
                tool_name,
                arguments
            )

            history_item = {
                "name": tool_name,
                "arguments": arguments,
                "result": result
            }

            tool_history.append(
                history_item
            )

            executed_any = True

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

        # -----------------------------------------
        # NOTHING NEW EXECUTED
        # -----------------------------------------

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

    if tool_history:

        return build_grounded_summary(
            user_request,
            tool_history
        )

    return (
        "CodeMate reached its maximum "
        "number of steps without completing "
        "the task."
    )


if __name__ == "__main__":

    print(
        run_agent(
            "Run buggy_test.py and fix it "
            "if necessary."
        )
    )