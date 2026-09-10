import os


MODEL = "qwen2.5-coder:3b"

MAX_AGENT_STEPS = 10

WORKSPACE = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "workspace"
    )
)