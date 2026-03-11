import logging
import urllib.parse
from fastapi import HTTPException, status
import httpx
from pydantic import ValidationError

from app.core.config import Config
from app.dtos.auth import OAuthCallbackRequest
from app.models.users import User
from app.repositories.user_repository import UserRepository
from app.services.jwt import JwtService

logger = logging.getLogger("oauth")

class OAuthService:
    def __init__(self, config: Config):
        self.config = config
        self.user_repo = UserRepository()
        self.jwt_service = JwtService()

    def get_google_auth_url(self) -> str:
        base_url = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            "client_id": self.config.GOOGLE_CLIENT_ID,
            "redirect_uri": self.config.GOOGLE_REDIRECT_URI,
            "response_type": "code",
            "scope": "openid email profile",
            "access_type": "offline",
            "prompt": "consent"
        }
        return f"{base_url}?{urllib.parse.urlencode(params)}"

    def get_kakao_auth_url(self) -> str:
        base_url = "https://kauth.kakao.com/oauth/authorize"
        params = {
            "client_id": self.config.KAKAO_CLIENT_ID,
            "redirect_uri": self.config.KAKAO_REDIRECT_URI,
            "response_type": "code",
        }
        return f"{base_url}?{urllib.parse.urlencode(params)}"

    async def handle_google_callback(self, code: str) -> dict:
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "client_id": self.config.GOOGLE_CLIENT_ID,
            "client_secret": self.config.GOOGLE_CLIENT_SECRET,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": self.config.GOOGLE_REDIRECT_URI,
        }
        
        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=data)
            if token_response.status_code != 200:
                logger.error(f"Google Token Error: {token_response.text}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to retrieve Google token")
            
            token_data = token_response.json()
            access_token = token_data.get("access_token")

            userinfo_url = "https://www.googleapis.com/oauth2/v2/userinfo"
            headers = {"Authorization": f"Bearer {access_token}"}
            user_response = await client.get(userinfo_url, headers=headers)
            
            if user_response.status_code != 200:
                logger.error(f"Google UserInfo Error: {user_response.text}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to retrieve Google user info")
            
            user_info = user_response.json()
            
        email = user_info.get("email")
        sns_id = user_info.get("id")
        name = user_info.get("name", "Google User")

        return await self._process_social_login(email, name, sns_id, "google")

    async def handle_kakao_callback(self, code: str) -> dict:
        token_url = "https://kauth.kakao.com/oauth/token"
        data = {
            "grant_type": "authorization_code",
            "client_id": self.config.KAKAO_CLIENT_ID,
            "client_secret": self.config.KAKAO_CLIENT_SECRET,
            "redirect_uri": self.config.KAKAO_REDIRECT_URI,
            "code": code,
        }
        
        async with httpx.AsyncClient() as client:
            token_response = await client.post(token_url, data=data)
            if token_response.status_code != 200:
                logger.error(f"Kakao Token Error: {token_response.text}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to retrieve Kakao token")
            
            token_data = token_response.json()
            access_token = token_data.get("access_token")

            userinfo_url = "https://kapi.kakao.com/v2/user/me"
            headers = {"Authorization": f"Bearer {access_token}"}
            user_response = await client.get(userinfo_url, headers=headers)
            
            if user_response.status_code != 200:
                logger.error(f"Kakao UserInfo Error: {user_response.text}")
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to retrieve Kakao user info")
            
            user_info = user_response.json()

        kakao_account = user_info.get("kakao_account", {})
        email = kakao_account.get("email")
        sns_id = str(user_info.get("id"))
        profile = kakao_account.get("profile", {})
        name = profile.get("nickname", "Kakao User")

        return await self._process_social_login(email, name, sns_id, "kakao")

    async def _process_social_login(self, email: str, name: str, sns_id: str, provider: str) -> dict:
        user = await self.user_repo.get_user_by_sns_id(sns_id, provider)
        
        if not user:
            if email:
                existing_user = await self.user_repo.get_user_by_email(email)
                if existing_user and existing_user.provider != provider:
                     logger.warning(f"Email {email} already used by provider {existing_user.provider}")
                     raise HTTPException(
                         status_code=status.HTTP_409_CONFLICT, 
                         detail=f"이미 {existing_user.provider}로 가입된 이메일입니다."
                     )
            
            user = await self.user_repo.create_social_user(
                email=email or f"{sns_id}@{provider}.com",
                name=name,
                sns_id=sns_id,
                provider=provider
            )
            
        await self.user_repo.update_last_login(user.id)
        tokens = self.jwt_service.issue_jwt_pair(user)
        return tokens
