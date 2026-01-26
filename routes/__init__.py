from fastapi import APIRouter, Request
from routes.v1 import v1_router

router = APIRouter(prefix="/api")


@router.get("/ip")
async def get_ip(request: Request):
    return {"ip": request.client.host}


router.include_router(v1_router)