# CLAUDE.md - Project Guide for AI Assistants

## Project Overview

**Basirat** is an AI-powered Muslim matrimonial app backend built with FastAPI. It features real-time compatibility scoring, safety monitoring, and chat functionality.

## Tech Stack

| Component | Technology | Free Tier |
|-----------|------------|-----------|
| Backend | Python 3.11 + FastAPI | - |
| Database | Neon PostgreSQL | 0.5GB |
| Cache | Upstash Redis | 10k cmds/day |
| Real-time | Firebase Realtime DB | 1GB |
| AI Models | Huggingface Inference API | Rate limited |
| Deployment | Render.com | 750 hrs/month |

## Project Structure

```
basirat-backend/
├── app/
│   ├── main.py              # FastAPI entry point
│   ├── config.py            # Pydantic settings
│   ├── core/
│   │   ├── security.py      # JWT, password hashing
│   │   ├── dependencies.py  # FastAPI dependencies
│   │   └── firebase.py      # Firebase Admin SDK
│   ├── db/
│   │   ├── session.py       # SQLAlchemy async session
│   │   └── redis.py         # Upstash Redis client
│   ├── models/              # SQLAlchemy ORM models
│   ├── schemas/             # Pydantic request/response schemas
│   ├── api/v1/              # API route handlers
│   ├── services/            # Business logic layer
│   └── ai/                  # AI/ML analysis modules
├── alembic/                 # Database migrations
├── tests/                   # Pytest tests
├── requirements.txt
├── render.yaml              # Deployment config
└── .env.example             # Environment template
```

## Key Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --reload

# Run with specific port
uvicorn app.main:app --reload --port 8000

# Run tests
pytest

# Format code
black app/
isort app/

# Create migration
alembic revision --autogenerate -m "description"

# Run migrations
alembic upgrade head
```

## Environment Setup

1. Copy `.env.example` to `.env`
2. Fill in credentials from:
   - Neon: https://console.neon.tech
   - Upstash: https://console.upstash.com
   - Firebase: https://console.firebase.google.com
   - Huggingface: https://huggingface.co/settings/tokens

## API Structure

Base URL: `/api/v1`

| Module | Prefix | Status |
|--------|--------|--------|
| Auth | `/auth` | ✅ Done |
| Profiles | `/profiles` | 🔲 TODO |
| Matching | `/matching` | 🔲 TODO |
| Chat | `/chat` | 🔲 TODO |
| AI Analysis | `/ai` | 🔲 TODO |
| Guardian | `/guardian` | 🔲 TODO |

## Database Models

- **User** - Authentication (phone, email, password_hash)
- **Profile** - Biodata (name, age, sect, religiosity, etc.)
- **PersonalityScore** - Big Five traits from chat analysis
- **Swipe** - User swipe actions (like/pass/super_like)
- **Match** - Matched pairs with Firebase chat reference
- **CompatibilityScore** - AI-generated Red/Green Zone scores
- **ChatMetadata** - Aggregated chat statistics
- **SafetyAlert** - Toxicity/harassment flags
- **GuardianLink** - Parent/Wali dashboard access

## Coding Conventions

### File Naming
- Models: `app/models/{entity}.py`
- Schemas: `app/schemas/{entity}.py`
- Routes: `app/api/v1/{entity}.py`
- Services: `app/services/{entity}_service.py`

### Import Order
```python
# Standard library
from datetime import datetime
from typing import Optional

# Third-party
from fastapi import APIRouter, Depends
from sqlalchemy import select

# Local
from app.config import settings
from app.models import User
```

### API Response Pattern
```python
# Success
{"data": {...}, "message": "Success"}

# Error
{"detail": "Error message"}

# List with pagination
{"data": [...], "total": 100, "page": 1, "per_page": 20}
```

### Authentication
- JWT access tokens (15 min expiry)
- Refresh tokens stored in Redis (7 days)
- Phone OTP verification required

## AI Features (Huggingface Models)

| Feature | Model | Purpose |
|---------|-------|---------|
| Sentiment | `cardiffnlp/twitter-roberta-base-sentiment-latest` | Message sentiment scoring |
| Toxicity | `unitary/toxic-bert` | Harassment detection |
| Personality | `Minej/bert-base-personality` | Big Five profiling |
| Embeddings | `sentence-transformers/all-MiniLM-L6-v2` | Language Style Matching |
| Chat | `mistralai/Mistral-7B-Instruct-v0.2` | Reply suggestions |

## Red/Green Zone Calculation

```python
score = (
    lsm_score * 0.30 +           # Language Style Matching
    (1 - sentiment_gap) * 0.25 + # Emotional investment balance
    engagement_ratio * 0.25 +     # Message ratio balance
    safety_score * 0.20           # No toxicity = 1.0
) * 100

# Zone thresholds
GREEN: score >= 70
YELLOW: 40 <= score < 70
RED: score < 40 OR toxicity_detected
```

## Common Tasks

### Adding a New Endpoint
1. Create schema in `app/schemas/{entity}.py`
2. Create route in `app/api/v1/{entity}.py`
3. Add router to `app/api/v1/router.py`
4. Add service logic in `app/services/{entity}_service.py`

### Adding a New Model
1. Create model in `app/models/{entity}.py`
2. Export in `app/models/__init__.py`
3. Create migration: `alembic revision --autogenerate`
4. Run migration: `alembic upgrade head`

### Testing an Endpoint
```bash
# Using httpie
http POST localhost:8000/api/v1/auth/register phone="+1234567890" password="test1234"

# Using curl
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"phone": "+1234567890", "password": "test1234"}'
```

## Important Notes

1. **Privacy First**: Chat text never stored on server, only metadata
2. **Edge AI**: Heavy processing designed for client-side (mobile)
3. **Free Tier Limits**: Be mindful of Upstash (10k/day) and Huggingface rate limits
4. **Islamic Context**: App is designed for Muslim matrimonial use with Halal considerations
5. **Guardian Mode**: Parents see safety dashboard, NOT chat content

## Troubleshooting

### Database Connection Issues
- Ensure Neon project is not paused (free tier pauses after 5 days inactivity)
- Check `?sslmode=require` in connection string

### Redis Connection Issues
- Upstash uses REST API, not standard Redis protocol
- Use `upstash-redis` package, not `redis`

### Firebase Issues
- Private key must have `\n` converted to actual newlines
- Check project ID matches Realtime Database URL
