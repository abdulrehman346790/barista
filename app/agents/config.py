"""
AI Agent Configuration
Uses Groq (primary) and Cerebras (backup) for FREE inference
Combined: 28,800 requests/day
"""

from openai import AsyncOpenAI
import os
from dotenv import load_dotenv

load_dotenv()

# ===========================================
# Groq Client (PRIMARY - 14,400 req/day FREE)
# Models: llama-3.1-8b-instant, llama-3.3-70b-versatile
# Base URL: https://api.groq.com/openai/v1
# ===========================================
groq_client = AsyncOpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# ===========================================
# Cerebras Client (BACKUP - 14,400 req/day FREE)
# Models: llama3.1-8b, llama-3.3-70b
# Base URL: https://api.cerebras.ai/v1
# ===========================================
cerebras_client = AsyncOpenAI(
    api_key=os.getenv("CEREBRAS_API_KEY"),
    base_url="https://api.cerebras.ai/v1"
)

# Model Configuration
MODELS = {
    "groq": {
        "fast": "llama-3.1-8b-instant",      # Quick tasks
        "smart": "llama-3.3-70b-versatile",   # Complex analysis
    },
    "cerebras": {
        "fast": "llama3.1-8b",
        "smart": "llama-3.3-70b",
    }
}


async def call_llm(
    system_prompt: str,
    user_prompt: str,
    use_smart: bool = False,
    max_tokens: int = 2000,
    temperature: float = 0.7
) -> str:
    """
    Call LLM with automatic fallback to Cerebras if Groq fails.
    This ensures high availability with 28,800 total requests/day.
    """

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    # Try Groq first
    try:
        model = MODELS["groq"]["smart" if use_smart else "fast"]
        response = await groq_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Groq failed: {e}, falling back to Cerebras...")

    # Fallback to Cerebras
    try:
        model = MODELS["cerebras"]["smart" if use_smart else "fast"]
        response = await cerebras_client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return response.choices[0].message.content
    except Exception as e2:
        print(f"Cerebras also failed: {e2}")
        raise Exception(f"Both AI providers failed. Groq error, Cerebras: {e2}")


async def call_llm_json(
    system_prompt: str,
    user_prompt: str,
    use_smart: bool = False,
    max_tokens: int = 2000,
) -> str:
    """
    Call LLM expecting JSON response.
    """
    # Add JSON instruction to system prompt
    json_system = system_prompt + "\n\nIMPORTANT: Respond with valid JSON only. No markdown, no extra text."

    return await call_llm(
        system_prompt=json_system,
        user_prompt=user_prompt,
        use_smart=use_smart,
        max_tokens=max_tokens,
        temperature=0.3  # Lower temperature for more consistent JSON
    )
