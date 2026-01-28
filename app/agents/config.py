"""
AI Agent Configuration
Uses Groq (primary) and Cerebras (backup) for FREE inference
Combined: 28,800 requests/day
"""

from agents import Agent, Runner, OpenAIChatCompletionsModel
from agents.run import RunConfig
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
        "fast": "llama-3.1-8b-instant",      # Quick tasks, 14,400/day
        "smart": "llama-3.3-70b-versatile",   # Complex analysis, 1,000/day
    },
    "cerebras": {
        "fast": "llama3.1-8b",
        "smart": "llama-3.3-70b",
    }
}

def get_model(use_smart: bool = False, provider: str = "groq"):
    """Get the appropriate model based on task complexity"""
    client = groq_client if provider == "groq" else cerebras_client
    model_type = "smart" if use_smart else "fast"
    model_name = MODELS[provider][model_type]

    return OpenAIChatCompletionsModel(
        model=model_name,
        openai_client=client
    )

def get_config(use_smart: bool = False, provider: str = "groq"):
    """Get RunConfig for agent execution"""
    client = groq_client if provider == "groq" else cerebras_client
    return RunConfig(
        model=get_model(use_smart, provider),
        model_provider=client,
        tracing_disabled=True
    )

async def run_with_fallback(agent: Agent, prompt: str, use_smart: bool = False):
    """
    Run agent with automatic fallback to Cerebras if Groq fails.
    This ensures high availability with 28,800 total requests/day.
    """
    try:
        # Try Groq first (faster)
        config = get_config(use_smart, "groq")
        result = await Runner.run(agent, prompt, run_config=config)
        return result.final_output
    except Exception as e:
        print(f"⚠️ Groq failed: {e}")
        print("🔄 Falling back to Cerebras...")
        try:
            # Fallback to Cerebras
            config = get_config(use_smart, "cerebras")
            result = await Runner.run(agent, prompt, run_config=config)
            return result.final_output
        except Exception as e2:
            print(f"❌ Cerebras also failed: {e2}")
            raise Exception(f"Both AI providers failed. Groq: {e}, Cerebras: {e2}")

def run_sync_with_fallback(agent: Agent, prompt: str, use_smart: bool = False):
    """Synchronous version for non-async contexts"""
    try:
        config = get_config(use_smart, "groq")
        result = Runner.run_sync(agent, prompt, run_config=config)
        return result.final_output
    except Exception as e:
        print(f"⚠️ Groq failed: {e}, falling back to Cerebras...")
        config = get_config(use_smart, "cerebras")
        result = Runner.run_sync(agent, prompt, run_config=config)
        return result.final_output
