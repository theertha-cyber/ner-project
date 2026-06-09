from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from src.gateway.services.auth_service import AuthService
from src.gateway.dependencies import get_db

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
async def login(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    return await service.login(
        email=payload["email"],
        password=payload["password"],
    )


@router.post("/refresh")
async def refresh(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    return await service.refresh(payload["refresh_token"])


@router.post("/logout")
async def logout(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    service = AuthService(db)
    token = payload.get("access_token", "")
    await service.logout(token)
    return {"message": "Logged out successfully"}
