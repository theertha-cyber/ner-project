from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from src.gateway.services.auth_service import AuthService
from src.gateway.dependencies import get_db
from src.shared.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _set_refresh_cookie(response: JSONResponse, token: str) -> None:
    response.set_cookie(
        "refresh_token",
        token,
        httponly=True,
        samesite="strict",
        path="/api/v1/auth/refresh",
        max_age=604800,
        secure=settings.environment == "production",
    )


@router.post("/login")
async def login(payload: dict, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    data = await service.login(email=payload["email"], password=payload["password"])
    response = JSONResponse({
        "access_token": data["access_token"],
        "token_type": data["token_type"],
        "user": data["user"],
    })
    _set_refresh_cookie(response, data["refresh_token"])
    return response


@router.post("/refresh")
async def refresh(request: Request, db: AsyncSession = Depends(get_db)):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        return JSONResponse(status_code=401, content={"detail": "No refresh token"})
    service = AuthService(db)
    data = await service.refresh(refresh_token)
    response = JSONResponse({
        "access_token": data["access_token"],
        "token_type": data["token_type"],
        "user": data["user"],
    })
    _set_refresh_cookie(response, data["refresh_token"])
    return response


@router.post("/logout")
async def logout(payload: dict, response: Response, db: AsyncSession = Depends(get_db)):
    service = AuthService(db)
    await service.logout(payload.get("access_token", ""))
    response.delete_cookie("refresh_token", path="/api/v1/auth/refresh")
    return {"message": "Logged out successfully"}
