from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.profiles import router as profiles_router
from app.api.v1.matching import router as matching_router
from app.api.v1.chat import router as chat_router
from app.api.v1.ai_analysis import router as ai_router
from app.api.v1.ai_coach import router as ai_coach_router
from app.api.v1.guardian import router as guardian_router

api_router = APIRouter()

# Include all route modules
api_router.include_router(auth_router)
api_router.include_router(profiles_router)
api_router.include_router(matching_router)
api_router.include_router(chat_router)
api_router.include_router(ai_router)
api_router.include_router(ai_coach_router)
api_router.include_router(guardian_router)
