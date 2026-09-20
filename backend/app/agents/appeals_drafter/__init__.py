"""appeals_drafter — parent agent package."""
# node.py is imported for its side effects + legacy shims
from app.agents.appeals_drafter import node as _node

# Re-export the LangGraph node and key shims
from app.agents.appeals_drafter.node import (
    _PROMPT,
    _build_user_message,
    _strip_code_fence,
    appeals_drafter_node,
    draft_appeal,
)
from app.agents.appeals_drafter.orchestrator import (
    SUB_AGENTS,
    AppealsDrafterAgent,
    appeals_drafter,
)
from app.agents.appeals_drafter.schemas import *  # noqa: F401,F403
from app.agents.appeals_drafter.sub_agents import *  # noqa: F401,F403
