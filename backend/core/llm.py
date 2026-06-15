import time
import re
import logging
from langchain_groq import ChatGroq
from backend.core.config import settings

logger = logging.getLogger("uvicorn.error")

class SafeChatGroq(ChatGroq):
    def invoke(self, input, *args, **kwargs):
        retries = 4
        for attempt in range(retries):
            try:
                return super().invoke(input, *args, **kwargs)
            except Exception as e:
                err_msg = str(e)
                if "429" in err_msg or "rate_limit" in err_msg:
                    wait_time = 8.0
                    match = re.search(r"try again in (\d+(?:\.\d+)?)s", err_msg)
                    if match:
                        wait_time = float(match.group(1)) + 1.5
                    logger.warning(f"Groq Rate Limit (429). Sleeping {wait_time}s before retrying (attempt {attempt + 1}/{retries})...")
                    time.sleep(wait_time)
                else:
                    raise e
        return super().invoke(input, *args, **kwargs)

# Create once at module load — not per call
_main_llm = SafeChatGroq(
    api_key=settings.GROQ_API_KEY,
    model=settings.GROQ_MAIN_MODEL,
    temperature=0.3,
    max_retries=3,
    request_timeout=30,
)

_fast_llm = SafeChatGroq(
    api_key=settings.GROQ_API_KEY,
    model=settings.GROQ_FAST_MODEL,
    temperature=0.4,
    max_retries=3,
    request_timeout=30,
)

def get_main_llm(temperature: float = 0.3) -> ChatGroq:
    return _main_llm

def get_fast_llm(temperature: float = 0.4) -> ChatGroq:
    return _fast_llm