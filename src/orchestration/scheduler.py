"""Task scheduler with DAG-based dependency resolution."""
from __future__ import annotations

from collections import defaultdict, deque
from typing import Any

import structlog

from src.agents.models import Task, TaskStatus

logger = structlog.get_logger(__name__)


class DependencyResolver:
    """Resolves task dependencies and provides topological ordering."""

    def topological_sort(self, tasks: list[Task]) -> list[list[Task]]:
        """Sort tasks into execution waves based on dependencies.

        Tasks in the same wave have no dependencies on each other and
        can be executed in parallel.

        Args:
            tasks: List of tasks with dependency information.

        Returns:
            List of waves, where each wave is a list of tasks that
            can be executed in parallel.

        Example:
            Input: task_1(no deps), task_2(deps=[task_1]), task_3(deps=[task_1])
            Output: [[task_1], [task_2, task_3]]
        """
        task_map = {t.id: t for t in tasks}
        in_degree: dict[str, int] = defaultdict(int)
        adjacency: dict[str, list[str]] = defaultdict(list)

        # Build dependency graph
        for task in tasks:
            if task.id not in in_degree:
                in_degree[task.id] = 0
            for dep in task.dependencies:
                adjacency[dep].append(task.id)
                in_degree[task.id] += 1

        # Kahn's algorithm for topological sort in waves
        waves: list[list[Task]] = []
        queue: deque[str] = deque(
            task_id for task_id, degree in in_degree.items() if degree == 0
        )

        while queue:
            wave_size = len(queue)
            wave: list[Task] = []
            for _ in range(wave_size):
                task_id = queue.popleft()
                if task_id in task_map:
                    wave.append(task_map[task_id])
                for dependent in adjacency[task_id]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)
            if wave:
                waves.append(wave)

        # Verify all tasks were scheduled
        scheduled = sum(len(w) for w in waves)
        if scheduled != len(tasks):
            raise ValueError(
                f"Could not schedule all tasks ({scheduled}/{len(tasks)}). "
                "Circular dependency detected."
            )

        return waves
