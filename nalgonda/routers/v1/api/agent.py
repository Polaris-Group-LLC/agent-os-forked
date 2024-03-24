import logging
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.params import Query

from nalgonda.dependencies.auth import get_current_user
from nalgonda.dependencies.dependencies import get_agent_manager
from nalgonda.models.agent_config import AgentConfig
from nalgonda.models.auth import User
from nalgonda.repositories.agent_config_firestore_storage import AgentConfigFirestoreStorage
from nalgonda.services.agent_manager import AgentManager
from nalgonda.services.env_vars_manager import ContextEnvVarsManager

logger = logging.getLogger(__name__)
agent_router = APIRouter(tags=["agent"])


# FIXME: agent name should be unique (agency-swarm gets it by name from settings.json).
# The current workaround: we append the owner id to the agent name to make it unique.
# Renaming is not supported yet.


@agent_router.get("/agent/list")
async def get_agent_list(
    current_user: Annotated[User, Depends(get_current_user)],
    storage: AgentConfigFirestoreStorage = Depends(AgentConfigFirestoreStorage),
) -> list[AgentConfig]:
    agents = storage.load_by_owner_id(current_user.id) + storage.load_by_owner_id(None)
    return agents


@agent_router.get("/agent")
async def get_agent_config(
    current_user: Annotated[User, Depends(get_current_user)],
    agent_id: str = Query(..., description="The unique identifier of the agent"),
    storage: AgentConfigFirestoreStorage = Depends(AgentConfigFirestoreStorage),
) -> AgentConfig:
    agent_config = storage.load_by_agent_id(agent_id)
    if not agent_config:
        logger.warning(f"Agent not found: {agent_id}, user: {current_user.id}")
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Agent not found")
    # check if the current user is the owner of the agent
    if agent_config.owner_id and agent_config.owner_id != current_user.id:
        logger.warning(f"User {current_user.id} does not have permissions to access agent: {agent_id}")
        raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Forbidden")
    return agent_config


@agent_router.put("/agent")
async def create_or_update_agent(
    current_user: Annotated[User, Depends(get_current_user)],
    agent_config: AgentConfig = Body(...),
    agent_manager: AgentManager = Depends(get_agent_manager),
    storage: AgentConfigFirestoreStorage = Depends(AgentConfigFirestoreStorage),
) -> dict[str, str]:
    # support template configs:
    if not agent_config.owner_id:
        logger.info(f"Creating agent for user: {current_user.id}, agent: {agent_config.name}")
        agent_config.agent_id = None
    else:
        # check if the current_user has permissions
        if agent_config.agent_id:
            agent_config_db = storage.load_by_agent_id(agent_config.agent_id)
            if not agent_config_db:
                logger.warning(f"Agent not found: {agent_config.agent_id}, user: {current_user.id}")
                raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail="Agent not found")
            if agent_config_db.owner_id != current_user.id:
                logger.warning(
                    f"User {current_user.id} does not have permissions to access agent: {agent_config.agent_id}"
                )
                raise HTTPException(status_code=HTTPStatus.FORBIDDEN, detail="Forbidden")
            # Ensure the agent name has not been changed
            if agent_config.name != agent_config_db.name:
                logger.warning(
                    f"Renaming agents is not supported yet: {agent_config.agent_id}, user: {current_user.id}"
                )
                raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail="Renaming agents is not supported yet")

    # Ensure the agent is associated with the current user
    agent_config.owner_id = current_user.id

    # Set the owner_id in the context variables
    ContextEnvVarsManager.set("owner_id", current_user.id)

    agent_id = await agent_manager.create_or_update_agent(agent_config)

    return {"agent_id": agent_id}
