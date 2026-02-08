"""API v1 routes"""
from fastapi import APIRouter
from routes.v1 import auth, users, transactions, messages, categories, chat, files

# Create v1 router
v1_router = APIRouter(prefix="/v1")

# Include all sub-routers
v1_router.include_router(auth.router)
v1_router.include_router(users.router)
v1_router.include_router(transactions.router)
v1_router.include_router(categories.router)
v1_router.include_router(messages.router)
v1_router.include_router(chat.router)
v1_router.include_router(files.router)
