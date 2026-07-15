from __future__ import annotations

from uuid import UUID

from mockmarket._base import BaseClient
from mockmarket.schemas import SandboxCreate, SandboxResponse, SandboxUpdate


class SandboxesClient(BaseClient):
    async def list(self) -> list[SandboxResponse]:
        data = await self._request("GET", "/api/v1/sandboxes")
        return [SandboxResponse.model_validate(item) for item in data]

    async def create(self, params: SandboxCreate) -> SandboxResponse:
        data = await self._request("POST", "/api/v1/sandboxes", json_body=params.model_dump())
        return SandboxResponse.model_validate(data)

    async def get(self, sandbox_id: UUID) -> SandboxResponse:
        data = await self._request("GET", f"/api/v1/sandboxes/{sandbox_id}")
        return SandboxResponse.model_validate(data)

    async def stop(self, sandbox_id: UUID) -> None:
        await self._request("DELETE", f"/api/v1/sandboxes/{sandbox_id}")

    async def update(self, sandbox_id: UUID, params: SandboxUpdate) -> SandboxResponse:
        data = await self._request(
            "PATCH",
            f"/api/v1/dashboard/sandboxes/{sandbox_id}",
            json_body=params.model_dump(exclude_none=True),
        )
        return SandboxResponse.model_validate(data)
