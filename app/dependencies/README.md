# Security Module Documentation

**파일 위치**: `app/dependencies/security.py`

## 📌 개요
이 모듈은 FastAPI 애플리케이션의 **인증(Authentication)** 및 **인가(Authorization)**를 처리하는 의존성(Dependency) 함수들을 정의합니다. 주로 JWT 토큰을 검증하고, 요청을 보낸 사용자를 식별하는 역할을 합니다.

## 🛠️ 주요 구성 요소

### 1. `security = HTTPBearer()`
- **역할**: FastAPI의 보안 스키마를 정의합니다.
- **동작**: 요청 헤더의 `Authorization: Bearer <token>` 값을 추출합니다.
- **Swagger UI**: 이 설정 덕분에 Swagger 문서에서 'Authorize' 버튼이 활성화되어 토큰을 입력할 수 있습니다.

### 2. `get_request_user` 함수

```python
async def get_request_user(credential: Annotated[HTTPAuthorizationCredentials, Depends(security)]) -> User:
```

- **역할**: 보호된 라우트(Protected Route)에 접근할 때 실행되는 의존성 함수입니다.
- **동작 과정**:
    1. **토큰 추출**: `HTTPAuthorizationCredentials`에서 Bearer 토큰을 가져옵니다.
    2. **토큰 검증**: `JwtService().verify_jwt`를 사용하여 토큰의 유효성을 검사합니다 (만료 여부, 서명 확인 등).
    3. **사용자 식별**: 토큰 페이로드(`payload`)에서 `user_id`를 추출합니다.
    4. **사용자 조회**: `UserRepository().get_user(user_id)`를 통해 DB에서 해당 ID의 사용자 정보를 가져옵니다.
    5. **결과 반환**: 유효한 사용자 객체(`User`)를 반환합니다.
- **예외 처리**: 사용자가 존재하지 않거나 토큰이 유효하지 않은 경우 `401 Unauthorized` 에러를 발생시킵니다.

## 🚀 사용 예시 (Router)

API 라우터에서 로그인한 사용자의 정보가 필요할 때 다음과 같이 사용합니다.

```python
from fastapi import APIRouter, Depends
from app.models.users import User
from app.dependencies.security import get_request_user

router = APIRouter()

@router.get("/me")
async def read_users_me(current_user: User = Depends(get_request_user)):
    return {"username": current_user.email, "id": current_user.id}
```

---

## 🍌 Nano Banana Pro 설명 (아주 쉽게 이해하기)

## 🍌 Nano Banana Pro 설명 (아주 쉽게 이해하기)

이제 코드 안에 직접 설명이 들어갔어요! (Docstring)

```python
async def get_request_user(credential: Annotated[HTTPAuthorizationCredentials, Depends(security)]) -> User:
    """
    [🍌 Nano Banana Pro 설명: 놀이공원 자유이용권 검사 과정]

    1. security = HTTPBearer() (입구 검사원):
       - 놀이공원(API) 입구에 서 있는 검사원입니다.
       - "손목 밴드(Toyken)"를 보여달라고 요구합니다.

    2. token (자유이용권 팔찌):
       - 손님이 차고 있는 팔찌입니다.
       - 여기에는 입장 날짜와 고객 번호가 적혀 있어요.

    3. JwtService().verify_jwt (위조 검사):
       - 검사원이 팔찌를 기계에 찍어봅니다.
       - "날짜가 지났는지?", "우리가 발급한 진짜 팔찌인지?" 확인합니다.

    4. user_id (고객 번호):
       - 팔찌 안에 들어있는 정보 중 "고객 고유 번호"를 읽어냅니다.

    5. UserRepository().get_user (회원 명부 확인):
       - 컴퓨터(DB)에서 그 고객 번호를 검색해 "실제로 등록된 회원인지" 확인합니다.

    6. return user (입장 허가):
       - 모든 확인이 끝나면 "네, 입장하세요!" 하고 손님(User)을 놀이기구(API)로 들여보냅니다.
    """
    token = credential.credentials
    # ... (나머지 코드)
```

