from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, status
from fastapi.responses import JSONResponse as Response
from fastapi.responses import RedirectResponse

from app.core import config
from app.core.config import Env
from app.dtos.auth import LoginRequest, LoginResponse, SignUpRequest, TokenRefreshResponse
from app.services.auth import AuthService
from app.services.jwt import JwtService

auth_router = APIRouter(prefix="/auth", tags=["auth"])


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


# ─── 카카오 OAuth 로그인 ─────────────────────────────────────


@auth_router.get("/kakao")
async def kakao_login():
    """카카오 로그인 페이지로 리다이렉트합니다."""
    kakao_auth_url = (
        "https://kauth.kakao.com/oauth/authorize"
        f"?client_id={config.KAKAO_CLIENT_ID}"
        f"&redirect_uri={config.KAKAO_REDIRECT_URI}"
        "&response_type=code"
    )
    return RedirectResponse(url=kakao_auth_url)


@auth_router.get("/kakao/callback")
async def kakao_callback(
    code: str,
    auth_service: Annotated[AuthService, Depends(AuthService)],
):
    """카카오 인가 코드를 받아 access_token을 발급하고, 사용자 정보를 조회하여 JWT를 발급합니다."""
    import httpx

    # 1) 인가 코드 → 카카오 access_token 교환
    token_url = "https://kauth.kakao.com/oauth/token"
    token_data = {
        "grant_type": "authorization_code",
        "client_id": config.KAKAO_CLIENT_ID,
        "client_secret": config.KAKAO_CLIENT_SECRET,
        "redirect_uri": config.KAKAO_REDIRECT_URI,
        "code": code,
    }

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(token_url, data=token_data)
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"카카오 토큰 발급 실패: {token_resp.text}",
            )
        kakao_tokens = token_resp.json()
        kakao_access_token = kakao_tokens["access_token"]

    # 2) 카카오 access_token → 사용자 정보 조회
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            "https://kapi.kakao.com/v2/user/me",
            headers={"Authorization": f"Bearer {kakao_access_token}"},
        )
        if user_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"카카오 사용자 정보 조회 실패: {user_resp.text}",
            )
        kakao_user = user_resp.json()

    # 3) 사용자 정보 파싱 (이메일 권한 없으므로 카카오 고유 ID 사용)
    kakao_id = kakao_user.get("id")  # 카카오 고유 사용자 ID (숫자)
    kakao_account = kakao_user.get("kakao_account", {})
    kakao_profile = kakao_account.get("profile", {})
    nickname = kakao_profile.get("nickname", "카카오사용자")

    if not kakao_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="카카오 사용자 ID를 가져올 수 없습니다.",
        )

    # 이메일 권한이 없으므로 카카오 ID 기반 가상 이메일 생성
    oauth_email = f"kakao_{kakao_id}@kakao.oauth"

    # 4) DB에 사용자가 없으면 자동 회원가입, 있으면 기존 사용자 로그인
    user = await auth_service.get_or_create_oauth_user(email=oauth_email, name=nickname, provider="kakao")

    # 5) JWT 발급
    tokens = await auth_service.login(user)
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


# ─── 구글 OAuth 로그인 ─────────────────────────────────────


@auth_router.get("/google")
async def google_login():
    """구글 로그인 페이지로 리다이렉트합니다."""
    google_auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={config.GOOGLE_CLIENT_ID}"
        f"&redirect_uri={config.GOOGLE_REDIRECT_URI}"
        "&response_type=code"
        "&scope=openid%20email%20profile"
    )
    return RedirectResponse(url=google_auth_url)


@auth_router.get("/google/callback")
async def google_callback(
    code: str,
    auth_service: Annotated[AuthService, Depends(AuthService)],
):
    """구글 인가 코드를 받아 access_token을 발급하고, 사용자 정보를 조회하여 JWT를 발급합니다."""
    import httpx

    # 1) 인가 코드 → 구글 access_token 교환
    token_url = "https://oauth2.googleapis.com/token"
    token_data = {
        "grant_type": "authorization_code",
        "client_id": config.GOOGLE_CLIENT_ID,
        "client_secret": config.GOOGLE_CLIENT_SECRET,
        "redirect_uri": config.GOOGLE_REDIRECT_URI,
        "code": code,
    }

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(token_url, data=token_data)
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"구글 토큰 발급 실패: {token_resp.text}",
            )
        google_tokens = token_resp.json()
        google_access_token = google_tokens["access_token"]

    # 2) 구글 access_token → 사용자 정보 조회
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {google_access_token}"},
        )
        if user_resp.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"구글 사용자 정보 조회 실패: {user_resp.text}",
            )
        google_user = user_resp.json()

    # 3) 사용자 정보 파싱
    email = google_user.get("email")
    name = google_user.get("name", "구글사용자")

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="구글 계정에서 이메일 정보를 가져올 수 없습니다.",
        )

    # 4) DB에 사용자가 없으면 자동 회원가입, 있으면 기존 사용자 로그인
    user = await auth_service.get_or_create_oauth_user(email=email, name=name, provider="google")

    # 5) JWT 발급
    tokens = await auth_service.login(user)
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
