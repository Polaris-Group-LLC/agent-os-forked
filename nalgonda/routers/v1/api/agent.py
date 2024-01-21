from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.params import Query

from nalgonda.dependencies.auth import get_current_active_user
from nalgonda.dependencies.dependencies import get_agent_manager
from nalgonda.models.agent_config import AgentConfig
from nalgonda.models.auth import UserInDB
from nalgonda.persistence.agent_config_firestore_storage import AgentConfigFirestoreStorage
from nalgonda.services.agent_manager import AgentManager

agent_router = APIRouter(tags=["agent"])


@agent_router.get("/agent")
async def get_agent_list(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    storage: AgentConfigFirestoreStorage = Depends(AgentConfigFirestoreStorage),
) -> list[AgentConfig]:
    agents = storage.load_by_user_id(current_user.id)
    return agents


@agent_router.get("/agent/config")
async def get_agent_config(
    agent_id: str = Query(..., description="The unique identifier of the agent"),
    storage: AgentConfigFirestoreStorage = Depends(AgentConfigFirestoreStorage),
) -> AgentConfig:
    config = storage.load_by_agent_id(agent_id)
    if not config:
        raise HTTPException(status_code=404, detail="Agent configuration not found")
    return config


@agent_router.put("/agent/config")
async def update_agent_config(
    current_user: Annotated[UserInDB, Depends(get_current_active_user)],
    agent_config: AgentConfig = Body(...),
    agent_manager: AgentManager = Depends(get_agent_manager),
) -> dict[str, str]:
    agent_config.owner_id = current_user.id  # Ensure the agent is associated with the user
    agent_id = await agent_manager.create_or_update_agent(agent_config)
    return {"agent_id": agent_id}
