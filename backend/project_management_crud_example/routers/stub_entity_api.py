"""API endpoints for stub entity management - template for creating real API endpoints."""

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status

from project_management_crud_example.dal.sqlite.repository import StubEntityRepository
from project_management_crud_example.dependencies import get_stub_entity_repo
from project_management_crud_example.domain_models import StubEntity, StubEntityCreateCommand, StubEntityData

router = APIRouter(prefix="/stub_entities", tags=["stub-entities"])


@router.post("", response_model=StubEntity, status_code=status.HTTP_201_CREATED)
async def create_stub_entity(
    stub_entity_data: StubEntityData,
    repo: StubEntityRepository = Depends(get_stub_entity_repo),  # noqa: B008
) -> StubEntity:
    """Create a new stub entity."""
    stub_entity_create_command = StubEntityCreateCommand(stub_entity_data=stub_entity_data)
    return repo.create_stub_entity(stub_entity_create_command)


@router.get("/{stub_entity_id}", response_model=StubEntity)
async def get_stub_entity(
    stub_entity_id: str,
    repo: StubEntityRepository = Depends(get_stub_entity_repo),  # noqa: B008
) -> StubEntity:
    """Get a stub entity by ID."""
    stub_entity = repo.get_stub_entity_by_id(stub_entity_id)
    if stub_entity is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stub entity not found")
    return stub_entity


@router.get("", response_model=List[StubEntity])
async def get_all_stub_entities(
    repo: StubEntityRepository = Depends(get_stub_entity_repo),  # noqa: B008
) -> List[StubEntity]:
    """Get all stub entities."""
    return repo.get_all_stub_entities()


@router.delete("/{stub_entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_stub_entity(
    stub_entity_id: str,
    repo: StubEntityRepository = Depends(get_stub_entity_repo),  # noqa: B008
) -> None:
    """Delete a stub entity by ID."""
    success = repo.delete_stub_entity(stub_entity_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Stub entity not found")
