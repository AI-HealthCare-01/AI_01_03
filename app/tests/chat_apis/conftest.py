"""
Chat API 테스트 전용 conftest.

DB 연결 없이 실행 가능하도록 상위 conftest의 DB fixture를 오버라이드합니다.
"""

import pytest


@pytest.fixture(scope="session", autouse=True)
def initialize():
    """상위 conftest의 DB initialize fixture를 오버라이드 (no-op)."""
    yield


@pytest.fixture(autouse=True, scope="session")
def event_loop():
    """상위 conftest의 event_loop fixture를 오버라이드 (no-op)."""
    pass
