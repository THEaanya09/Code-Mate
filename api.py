from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv

import os
import time

from agent import run_agent
from logger import logger


load_dotenv()


API_KEY = os.getenv(
    "CODEMATE_API_KEY"
)

MAX_MESSAGE_LENGTH = 2000


app = FastAPI(
    title="CodeMate API",
    description="AI-powered terminal coding agent",
    version="1.0.0"
)


class ChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=MAX_MESSAGE_LENGTH
    )


def verify_api_key(
    api_key: str | None
):

    if not API_KEY:

        raise HTTPException(
            status_code=500,
            detail="API key is not configured."
        )

    if api_key != API_KEY:

        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key."
        )


@app.get("/health")
def health():

    logger.info(
        "GET /health | SUCCESS"
    )

    return {
        "status": "ok",
        "service": "CodeMate"
    }


@app.post("/chat")
def chat(
    request: ChatRequest,
    x_api_key: str | None = Header(
        default=None
    )
):

    start_time = time.perf_counter()

    verify_api_key(
        x_api_key
    )

    message = request.message.strip()

    if not message:

        logger.warning(
            "POST /chat | EMPTY MESSAGE"
        )

        raise HTTPException(
            status_code=400,
            detail="Message cannot be empty."
        )

    if len(message) > MAX_MESSAGE_LENGTH:

        logger.warning(
            "POST /chat | MESSAGE TOO LARGE | length=%d",
            len(message)
        )

        raise HTTPException(
            status_code=413,
            detail=f"Message is too large. Maximum length is {MAX_MESSAGE_LENGTH} characters."
        )

    logger.info(
        "POST /chat | REQUEST | message=%s",
        message
    )

    try:

        response = run_agent(
            message
        )

        duration = time.perf_counter() - start_time

        logger.info(
            "POST /chat | SUCCESS | duration=%.2fs",
            duration
        )

        return {
            "response": response
        }

    except Exception:

        duration = time.perf_counter() - start_time

        logger.exception(
            "POST /chat | ERROR | duration=%.2fs",
            duration
        )

        raise HTTPException(
            status_code=500,
            detail="Internal server error."
        )