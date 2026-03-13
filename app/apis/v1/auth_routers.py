from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from fastapi.responses import JSONResponse as Response
from fastapi.responses import RedirectResponse

from app.core import config
from app.core.config import Env
from app.dtos.auth import LoginRequest, LoginResponse, OAuthUrlResponse, SignUpRequest, TokenRefreshResponse
from app.services.auth import AuthService
from app.services.jwt import JwtService
from app.services.oauth import OAuthService

auth_router = APIRouter(prefix="/auth", tags=["auth"])


def get_oauth_service() -> OAuthService:
    return OAuthService(config)


@auth_router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    request: SignUpRequest,
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> Response:
    await auth_service.signup(request)
    return Response(content={"detail": "회원가입이 성공적으로 완료되었습니다."}, status_code=status.HTTP_201_CREATED)


@auth_router.post("/login", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def login(
    request: LoginRequest,
    auth_service: Annotated[AuthService, Depends(AuthService)],
) -> Response:
    user = await auth_service.authenticate(request)
    tokens = await auth_service.login(user)
    resp = Response(
        content=LoginResponse(access_token=str(tokens["access_token"])).model_dump(), status_code=status.HTTP_200_OK
    )
    resp.set_cookie(
        key="refresh_token",
        value=str(tokens["refresh_token"]),
        httponly=True,
        secure=True if config.ENV == Env.PROD else False,
        domain=config.COOKIE_DOMAIN or None,
        expires=tokens["access_token"].payload["exp"],
    )
    return resp


@auth_router.get("/token/refresh", response_model=TokenRefreshResponse, status_code=status.HTTP_200_OK)
async def token_refresh(
    jwt_service: Annotated[JwtService, Depends(JwtService)],
    refresh_token: Annotated[str | None, Cookie()] = None,
) -> Response:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token is missing.")
    access_token = jwt_service.refresh_jwt(refresh_token)
    return Response(
        content=TokenRefreshResponse(access_token=str(access_token)).model_dump(), status_code=status.HTTP_200_OK
    )


@auth_router.get("/kakao/login", status_code=status.HTTP_302_FOUND)
async def kakao_auth_redirect(oauth_service: Annotated[OAuthService, Depends(get_oauth_service)]) -> RedirectResponse:
    url = oauth_service.get_kakao_auth_url()
    return RedirectResponse(url=url, status_code=302)


@auth_router.get("/google/login", status_code=status.HTTP_302_FOUND)
async def google_auth_redirect(oauth_service: Annotated[OAuthService, Depends(get_oauth_service)]) -> RedirectResponse:
    url = oauth_service.get_google_auth_url()
    return RedirectResponse(url=url, status_code=302)


@auth_router.get("/google", response_model=OAuthUrlResponse, status_code=status.HTTP_200_OK)
async def google_auth_url(oauth_service: Annotated[OAuthService, Depends(get_oauth_service)]) -> Response:
    url = oauth_service.get_google_auth_url()
    return Response(content=OAuthUrlResponse(url=url).model_dump(), status_code=status.HTTP_200_OK)


@auth_router.get("/google/callback", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def google_auth_callback(
    code: str,
    oauth_service: Annotated[OAuthService, Depends(get_oauth_service)],
) -> Response:
    tokens = await oauth_service.handle_google_callback(code)
    resp = Response(
        content=LoginResponse(access_token=str(tokens["access_token"])).model_dump(),
        status_code=status.HTTP_200_OK,
    )
    resp.set_cookie(
        key="refresh_token",
        value=str(tokens["refresh_token"]),
        httponly=True,
        secure=True if config.ENV == Env.PROD else False,
        domain=config.COOKIE_DOMAIN or None,
        expires=tokens["access_token"].payload["exp"],
    )
    return resp


@auth_router.get("/kakao", response_model=OAuthUrlResponse, status_code=status.HTTP_200_OK)
async def kakao_auth_url(oauth_service: Annotated[OAuthService, Depends(get_oauth_service)]) -> Response:
    url = oauth_service.get_kakao_auth_url()
    return Response(content=OAuthUrlResponse(url=url).model_dump(), status_code=status.HTTP_200_OK)


@auth_router.get("/kakao/callback", response_model=LoginResponse, status_code=status.HTTP_200_OK)
async def kakao_auth_callback(
    code: str,
    oauth_service: Annotated[OAuthService, Depends(get_oauth_service)],
) -> Response:
    tokens = await oauth_service.handle_kakao_callback(code)
    resp = Response(
        content=LoginResponse(access_token=str(tokens["access_token"])).model_dump(),
        status_code=status.HTTP_200_OK,
    )
    resp.set_cookie(
        key="refresh_token",
        value=str(tokens["refresh_token"]),
        httponly=True,
        secure=True if config.ENV == Env.PROD else False,
        domain=config.COOKIE_DOMAIN or None,
        expires=tokens["access_token"].payload["exp"],
    )
    return resp
