"""Shared FastAPI dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.offers import AgentServices


async def get_db(request: Request) -> AsyncIterator[AsyncSession]:
    async with request.app.state.sessionmaker() as session:
        yield session


def get_services(request: Request) -> AgentServices:
    services: AgentServices = request.app.state.services
    return services


def client_address(request: Request) -> str:
    return request.client.host if request.client else "unknown"
