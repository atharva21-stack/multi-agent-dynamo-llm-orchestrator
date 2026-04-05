"""Agent registry for managing agent instances."""
from __future__ import annotations

from typing import Any

import structlog

from src.agents.base import AgentConfig, BaseAgent

logger = structlog.get_logger(__name__)


class AgentRegistry:
    """Registry for agent instances and factories.

    Allows dynamic registration and lookup of agent types.

    Example:
        registry = AgentRegistry()
        registry.register_agent("planning", PlanningAgent)
        agent = registry.get_agent("planning", config)
    """

    def __init__(self) -> None:
        self._registry: dict[str, type[BaseAgent]] = {}

    def register_agent(self, agent_type: str, agent_class: type[BaseAgent]) -> None:
        """Register an agent class under a type name.

        Args:
            agent_type: String identifier (e.g., "planning").
            agent_class: Agent class to instantiate on demand.
        """
        self._registry[agent_type] = agent_class
        logger.debug("agent_registered", agent_type=agent_type, class_name=agent_class.__name__)

    def get_agent(self, agent_type: str, config: AgentConfig | None = None) -> BaseAgent:
        """Create and return an agent instance by type.

        Args:
            agent_type: String identifier registered via register_agent.
            config: Optional config override; defaults are used if None.

        Returns:
            New agent instance.

        Raises:
            KeyError: If agent_type is not registered.
        """
        if agent_type not in self._registry:
            available = list(self._registry.keys())
            raise KeyError(
                f"Agent type '{agent_type}' not registered. Available: {available}"
            )
        cls = self._registry[agent_type]
        if config is None:
            config = AgentConfig(name=agent_type)
        return cls(config=config)

    def list_agents(self) -> list[str]:
        """Return all registered agent type names."""
        return list(self._registry.keys())

    def is_registered(self, agent_type: str) -> bool:
        """Check if an agent type is registered."""
        return agent_type in self._registry


# Global default registry
_default_registry: AgentRegistry | None = None


def get_registry() -> AgentRegistry:
    """Get the global agent registry, initializing it with defaults on first call."""
    global _default_registry
    if _default_registry is None:
        _default_registry = AgentRegistry()
        _register_defaults(_default_registry)
    return _default_registry


def _register_defaults(registry: AgentRegistry) -> None:
    """Register all built-in agent types."""
    from src.agents.planning_agent import PlanningAgent
    from src.agents.research_agent import ResearchAgent
    from src.agents.execution_agent import ExecutionAgent
    from src.agents.validation_agent import ValidationAgent

    registry.register_agent("planning", PlanningAgent)
    registry.register_agent("research", ResearchAgent)
    registry.register_agent("execution", ExecutionAgent)
    registry.register_agent("validation", ValidationAgent)
