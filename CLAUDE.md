# CLAUDE.md - Basirat AI Backend Project Guide

## Project Overview

**Basirat** is an AI-powered Muslim matrimonial app with an intelligent **AI Relationship Coach**. The AI observes conversations and provides **private insights** to each user - it does NOT write messages for users to preserve authentic human interaction.

---

## 🎯 Core AI Philosophy

```
✅ AI CAN:                      ❌ AI CANNOT:
─────────────                   ─────────────
• Read conversations            • Write messages for users
• Analyze patterns              • Send on user's behalf
• Give private insights         • Auto-reply
• Suggest TOPICS                • Suggest full messages
• Warn about red flags          • Make decisions for users
• Encourage authenticity        • Share User A's analysis with User B
```

**Why?** If AI writes messages for both users, conversations become AI-to-AI, leading to fake personas and bad marriages.

---

## 🏗 Tech Stack

| Component | Technology | Free Tier |
|-----------|------------|-----------|
| Backend | Python 3.11 + FastAPI | - |
| Database | Neon PostgreSQL | 0.5GB |
| Cache | Upstash Redis | 10k cmds/day |
| Real-time | Firebase Realtime DB | 1GB |
| **AI (Primary)** | **Groq API** | **14,400 req/day** |
| **AI (Backup)** | **Cerebras API** | **14,400 req/day** |
| AI Framework | OpenAI Agents SDK | - |
| Deployment | Render.com | 750 hrs/month |

---

## 🤖 AI Multi-Agent Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    BASIRAT AI BRAIN                             │
│              (OpenAI Agents SDK + Groq/Cerebras)                │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │              🎯 ORCHESTRATOR AGENT                       │    │
│  │         (Main Agent - Routes to Sub-Agents)              │    │
│  └─────────────────────────┬───────────────────────────────┘    │
│                            │                                     │
│      ┌─────────────────────┼─────────────────────┐              │
│      │                     │                     │              │
│      ▼                     ▼                     ▼              │
│ ┌─────────────┐     ┌─────────────┐     ┌─────────────┐        │
│ │  MATCHMAKER │     │  ANALYZER   │     │   COACH     │        │
│ │    AGENT    │     │    AGENT    │     │   AGENT     │        │
│ │             │     │             │     │ (Per User)  │        │
│ │ • Profile   │     │ • Read chat │     │ • Private   │        │
│ │   matching  │     │ • Patterns  │     │   insights  │        │
│ │ • Suggest   │     │ • Red flags │     │ • Tips      │        │
│ │   profiles  │     │ • Sentiment │     │ • Alerts    │        │
│ └─────────────┘     └─────────────┘     └─────────────┘        │
│                                                                  │
│ ┌─────────────┐     ┌─────────────┐     ┌─────────────┐        │
│ │   SAFETY    │     │ PERSONALITY │     │   TOPIC     │        │
│ │   AGENT     │     │   PROFILER  │     │  SUGGESTER  │        │
│ │             │     │             │     │             │        │
│ │ • Toxicity  │     │ • Traits    │     │ • Suggest   │        │
│ │ • Scam      │     │ • Values    │     │   topics    │        │
│ │ • Catfish   │     │ • Interests │     │ • NOT msgs  │        │
│ └─────────────┘     └─────────────┘     └─────────────┘        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📁 Project Structure

```
basirat-backend/
├── app/
│   ├── main.py                 # FastAPI entry point
│   ├── config.py               # Pydantic settings
│   │
│   ├── core/
│   │   ├── security.py         # JWT, password hashing
│   │   ├── dependencies.py     # FastAPI dependencies
│   │   └── firebase.py         # Firebase Admin SDK
│   │
│   ├── db/
│   │   ├── session.py          # SQLAlchemy async session
│   │   └── redis.py            # Upstash Redis client
│   │
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── user.py
│   │   ├── profile.py
│   │   ├── match.py
│   │   ├── message.py
│   │   └── ai_insight.py       # NEW
│   │
│   ├── schemas/                # Pydantic request/response
│   │
│   ├── api/v1/                 # API route handlers
│   │   ├── auth.py
│   │   ├── profiles.py
│   │   ├── matching.py
│   │   ├── chat.py
│   │   └── ai.py               # NEW - AI endpoints
│   │
│   ├── services/               # Business logic
│   │   ├── auth_service.py
│   │   ├── profile_service.py
│   │   ├── matching_service.py
│   │   └── ai_service.py       # NEW
│   │
│   └── agents/                 # NEW - AI Agents
│       ├── __init__.py
│       ├── config.py           # Groq/Cerebras setup
│       ├── base_agent.py
│       ├── orchestrator.py
│       ├── matchmaker.py
│       ├── analyzer.py
│       ├── coach.py
│       ├── safety.py
│       └── profiler.py
│
├── alembic/                    # Database migrations
├── tests/
├── requirements.txt
├── CLAUDE.md                   # This file
└── .env
```

---

## 🔑 Environment Variables

```bash
# ===========================================
# AI API Keys (FREE Tiers - 14,400 req/day each)
# ===========================================

# Groq API (PRIMARY)
# Get key from: https://console.groq.com
GROQ_API_KEY=your-groq-api-key

# Cerebras API (BACKUP)
# Get key from: https://cloud.cerebras.ai
CEREBRAS_API_KEY=your-cerebras-api-key

# AI Model Settings
AI_PRIMARY_MODEL=llama-3.1-8b-instant
AI_SMART_MODEL=llama-3.3-70b-versatile

# ===========================================
# Other Keys (existing)
# ===========================================
DATABASE_URL=postgresql://...
UPSTASH_REDIS_URL=...
FIREBASE_PROJECT_ID=...
SECRET_KEY=...
```

---

## 🛠 AI Agent Configuration

### File: `app/agents/config.py`

```python
from agents import Agent, Runner, OpenAIChatCompletionsModel
from agents.run import RunConfig
from openai import AsyncOpenAI
import os

# ===========================================
# Groq Client (PRIMARY - 14,400 req/day FREE)
# ===========================================
groq_client = AsyncOpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1"
)

# ===========================================
# Cerebras Client (BACKUP - 14,400 req/day FREE)
# ===========================================
cerebras_client = AsyncOpenAI(
    api_key=os.getenv("CEREBRAS_API_KEY"),
    base_url="https://api.cerebras.ai/v1"
)

# Model names
FAST_MODEL = "llama-3.1-8b-instant"      # Quick tasks
SMART_MODEL = "llama-3.3-70b-versatile"  # Complex analysis

def get_model(use_smart=False, client=groq_client):
    model_name = SMART_MODEL if use_smart else FAST_MODEL
    return OpenAIChatCompletionsModel(
        model=model_name,
        openai_client=client
    )

def get_config(use_smart=False):
    return RunConfig(
        model=get_model(use_smart),
        model_provider=groq_client,
        tracing_disabled=True
    )

# Fallback to Cerebras if Groq fails
async def run_with_fallback(agent, prompt, use_smart=False):
    try:
        config = RunConfig(
            model=get_model(use_smart, groq_client),
            model_provider=groq_client,
            tracing_disabled=True
        )
        return await Runner.run(agent, prompt, run_config=config)
    except Exception as e:
        print(f"Groq failed, falling back to Cerebras: {e}")
        config = RunConfig(
            model=get_model(use_smart, cerebras_client),
            model_provider=cerebras_client,
            tracing_disabled=True
        )
        return await Runner.run(agent, prompt, run_config=config)
```

---

## 🤖 Agent Definitions

### 1. Matchmaker Agent (`app/agents/matchmaker.py`)

```python
MATCHMAKER_INSTRUCTIONS = """
You are the Basirat Matchmaker Agent.

Analyze profiles and calculate compatibility based on:
1. Religious Compatibility (30%) - Sect, religiosity, prayer habits
2. Life Goals (25%) - Children, career, relocation
3. Family Values (20%) - Traditional vs modern views
4. Personality (15%) - Communication style
5. Practical (10%) - Age, location, education

OUTPUT JSON:
{
    "compatibility_score": 0-100,
    "zone": "green/yellow/red",
    "strengths": ["...", "...", "..."],
    "concerns": ["..."],
    "conversation_starters": ["topic1", "topic2"]
}
"""
```

### 2. Conversation Analyzer (`app/agents/analyzer.py`)

```python
ANALYZER_INSTRUCTIONS = """
You are the Basirat Conversation Analyzer.

READ and ANALYZE conversations (NEVER write messages).

Detect:
1. Interest levels (response time, question ratio, engagement)
2. Red flags (inconsistency, pressure, love bombing)
3. Personality traits (formal/casual, emotional expression)

OUTPUT JSON:
{
    "interest_level": {"user_a": 0-100, "user_b": 0-100},
    "red_flags": [],
    "personality_traits": {"user_a": [], "user_b": []},
    "private_insights": {
        "for_user_a": "...",
        "for_user_b": "..."
    },
    "suggested_topics": []
}
"""
```

### 3. Relationship Coach (`app/agents/coach.py`)

```python
def get_coach_instructions(user_name: str):
    return f"""
You are a PRIVATE Relationship Coach for {user_name}.

CRITICAL RULES:
1. Everything is PRIVATE to {user_name} only
2. NEVER reveal other person's private thoughts
3. Be supportive but HONEST

CAPABILITIES:
- Give private insights about the conversation
- Gentle warnings about concerns
- Encouragement for good communication
- Topic suggestions (NOT full messages)

NEVER write full messages for them!
"""
```

### 4. Safety Agent (`app/agents/safety.py`)

```python
SAFETY_INSTRUCTIONS = """
You are the Basirat Safety Guardian.

Detect:
1. Scam patterns (money requests, investment schemes)
2. Catfishing (refuses video calls, inconsistent details)
3. Manipulation (love bombing, guilt tripping, control)
4. Inappropriate content (explicit, harassment, threats)

ALERT LEVELS:
- GREEN: All normal
- YELLOW: Minor concern, inform user
- RED: Serious concern, strong warning
- BLACK: Report to admin, potential ban

OUTPUT JSON:
{
    "safety_score": 0-100,
    "alert_level": "green/yellow/red/black",
    "concerns": [],
    "recommended_action": ""
}
"""
```

---

## 📡 API Endpoints

### AI Endpoints (`app/api/v1/ai.py`)

```python
from fastapi import APIRouter, Depends

router = APIRouter(prefix="/api/v1/ai", tags=["AI"])

@router.post("/compatibility/{match_id}")
async def get_compatibility(match_id: str):
    """Get AI compatibility analysis"""
    pass

@router.post("/coach/ask")
async def ask_coach(match_id: str, question: str):
    """Ask AI coach a private question"""
    pass

@router.get("/insights/{match_id}")
async def get_insights(match_id: str):
    """Get AI insights for conversation"""
    pass

@router.post("/analyze/{match_id}")
async def analyze_conversation(match_id: str):
    """Trigger conversation analysis"""
    pass

@router.get("/safety/{match_id}")
async def safety_check(match_id: str):
    """Get safety analysis"""
    pass
```

### Existing Endpoints

| Module | Prefix | Status |
|--------|--------|--------|
| Auth | `/api/v1/auth` | ✅ Done |
| Profiles | `/api/v1/profiles` | ✅ Done |
| Matching | `/api/v1/matching` | 🔲 TODO |
| Chat | `/api/v1/chat` | 🔲 TODO |
| **AI** | `/api/v1/ai` | 🔲 TODO |

---

## 🗄 Database Schema (New Tables)

```sql
-- AI Insights (Private per user)
CREATE TABLE ai_insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    match_id UUID REFERENCES matches(id),
    insight_type VARCHAR(50),  -- 'tip', 'warning', 'encouragement'
    content TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Conversation Analysis Cache
CREATE TABLE conversation_analysis (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID REFERENCES matches(id),
    analysis_data JSONB,
    red_flags JSONB,
    interest_levels JSONB,  -- {"user_a": 85, "user_b": 72}
    last_analyzed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- AI Messages (Private @AI queries)
CREATE TABLE ai_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id UUID REFERENCES matches(id),
    user_id UUID REFERENCES users(id),
    query TEXT,
    response TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Personality Profiles
CREATE TABLE personality_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    traits JSONB,
    communication_style VARCHAR(50),
    values JSONB,
    updated_at TIMESTAMP
);
```

---

## 💬 AI Coach Interaction (Mobile App)

### Method 1: Floating Button
- Draggable button on chat screen
- Opens dedicated AI conversation screen
- Full context available

### Method 2: @Mention in Chat
- Type `@AI` in chat
- Message goes to AI, NOT to match
- Response visible ONLY to sender
- Visual indicator (🔒) shows private

### Method 3: Auto Insights Bar
- AI automatically shows relevant tips
- Dismissible notification bar

---

## 🔧 Key Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload --port 8000

# Run tests
pytest

# Create migration
alembic revision --autogenerate -m "add ai tables"

# Run migrations
alembic upgrade head
```

---

## 📅 Implementation Phases

### Phase 1: Core (Current)
- [x] Auth system
- [x] Profile CRUD
- [ ] Real-time chat (Firebase)
- [ ] Push notifications

### Phase 2: Basic AI
- [ ] Agent structure setup
- [ ] Groq/Cerebras integration
- [ ] Matchmaker agent
- [ ] Basic compatibility API

### Phase 3: AI Coach
- [ ] Coach agent (per user)
- [ ] @Mention handler
- [ ] Private insights storage
- [ ] Auto tips generation

### Phase 4: Safety & Analysis
- [ ] Conversation analyzer
- [ ] Safety agent
- [ ] Red flag detection
- [ ] Interest level tracking

### Phase 5: Advanced
- [ ] Personality profiler
- [ ] Authenticity scoring
- [ ] Advanced insights
- [ ] Topic suggestions

---

## 🧮 Request Calculation

| Feature | Requests/User/Day | 100 Users | 1000 Users |
|---------|-------------------|-----------|------------|
| Profile Analysis | 1 | 100 | 1,000 |
| Conversation Analysis | 5 | 500 | 5,000 |
| Private Coaching | 3 | 300 | 3,000 |
| Matching | 2 | 200 | 2,000 |
| **TOTAL** | **11** | **1,100** | **11,000** |

**Free Limit: 14,400/day (Groq) + 14,400/day (Cerebras) = 28,800/day**

---

## 🔐 Privacy Rules

1. AI insights are **PRIVATE** to each user
2. `@AI` messages **NEVER** sent to match
3. AI cannot share User A's analysis with User B
4. All AI interactions logged for transparency
5. Clear visual indicators for private content

---

## 🐛 Troubleshooting

### Groq API Issues
```python
# Check rate limits
# Free tier: 14,400 requests/day, 6,000 tokens/min

# If rate limited, fallback to Cerebras
try:
    result = await groq_call()
except RateLimitError:
    result = await cerebras_call()
```

### Database Connection
- Neon pauses after 5 days inactivity
- Check `?sslmode=require` in connection string

### Redis Issues
- Upstash uses REST API, not standard Redis
- Use `upstash-redis` package

---

## 📚 Resources

- [Groq Console](https://console.groq.com)
- [Cerebras Cloud](https://cloud.cerebras.ai)
- [OpenAI Agents SDK](https://github.com/openai/openai-agents-python)
- [FastAPI Docs](https://fastapi.tiangolo.com)
- [Neon PostgreSQL](https://neon.tech)
