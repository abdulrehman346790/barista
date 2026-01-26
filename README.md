---
title: Basirat API
emoji: 💑
colorFrom: green
colorTo: blue
sdk: docker
app_port: 7860
pinned: false
---

# Basirat - AI-Powered Muslim Matrimonial API

An intelligent matchmaking backend with real-time compatibility scoring, safety monitoring, and chat features.

## Features

- 🔐 **Authentication** - Phone + OTP verification, JWT tokens
- 👤 **Profiles** - Complete biodata management with Islamic-specific fields
- 💕 **Matching** - Swipe-based matching with mutual likes
- 💬 **Chat** - Firebase Realtime Database integration
- 🤖 **AI Analysis** - Compatibility scoring (Red/Green Zone)
- 🛡️ **Safety** - Toxicity detection using Huggingface models
- 👨‍👩‍👧 **Guardian Mode** - Privacy-preserving Wali dashboard

## Tech Stack

- **Backend**: Python + FastAPI
- **Database**: Neon PostgreSQL
- **Cache**: Upstash Redis
- **Real-time**: Firebase Realtime DB
- **AI**: Huggingface Inference API

## API Documentation

Once deployed, access the interactive docs at:
- Swagger UI: `/docs`
- ReDoc: `/redoc`

## Endpoints

| Module | Endpoints | Description |
|--------|-----------|-------------|
| Auth | 7 | Register, login, OTP, tokens |
| Profiles | 6 | CRUD, photos, verification |
| Matching | 5 | Discover, swipe, matches |
| Chat | 4 | Firebase tokens, metadata |
| AI | 5 | Compatibility, coaching, safety |
| Guardian | 8 | Wali dashboard, alerts |

## Environment Variables

Set these in Huggingface Space Settings → Variables:

```
SECRET_KEY=your-secret-key
DATABASE_URL=postgresql://...
UPSTASH_REDIS_URL=https://...
UPSTASH_REDIS_TOKEN=...
FIREBASE_PROJECT_ID=...
FIREBASE_PRIVATE_KEY=...
FIREBASE_CLIENT_EMAIL=...
HF_TOKEN=hf_...
```

## License

MIT
