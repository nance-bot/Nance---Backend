import json
import re
from langchain_core.runnables import RunnableLambda, RunnableBranch
from langchain_groq import ChatGroq
from dotenv import load_dotenv
load_dotenv()

def safe_extract_json(text):
    """
    Safely extract a JSON object from a string, handling code blocks and partial JSON.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Extract JSON block between ```json ... ```
        match = re.search(r"```json\s*(\{.*?\})\s*```", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
        # Try any JSON-looking object in the string
        match = re.search(r"(\{.*\})", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass
    raise ValueError("Failed to parse LLM response as JSON.")


# Expose a default LLM as a Runnable for chaining
llm = ChatGroq(model="qwen/qwen3-32b", temperature=0.2, max_retries=1)