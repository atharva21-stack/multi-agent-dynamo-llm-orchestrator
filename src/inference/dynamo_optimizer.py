"""PyTorch Dynamo-based batch scheduling optimizer.

Optimizes inference batch scheduling to maximize GPU utilization
by grouping requests with similar token lengths.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


@dataclass
class BatchSchedule:
    """Result of batch schedule optimization."""

    batches: list[list[int]] = field(default_factory=list)  # indices per batch
    estimated_throughput: float = 0.0  # tokens/second
    cost_reduction_pct: float = 0.0
    total_requests: int = 0
    total_batches: int = 0


class DynamoOptimizer:
    """Optimizes token batching for maximum GPU throughput.

    Uses a bin-packing approach to group requests with similar
    token counts into batches that fit within hardware limits.

    Example:
        optimizer = DynamoOptimizer()
        token_counts = [512, 1024, 256, 768, 512]
        schedule = optimizer.optimize_batch_schedule(token_counts, max_batch_size=4)
        # Returns BatchSchedule with grouped indices
    """

    def __init__(
        self,
        max_sequence_length: int = 4096,
        tokens_per_second_per_gpu: float = 50000.0,
    ) -> None:
        self.max_sequence_length = max_sequence_length
        self.tokens_per_second_per_gpu = tokens_per_second_per_gpu
        self._dynamo_compiled = False

    def optimize_batch_schedule(
        self,
        token_counts: list[int],
        max_batch_size: int = 32,
        max_batch_tokens: int = 16384,
    ) -> BatchSchedule:
        """Create optimal batching schedule from token count list.

        Uses a first-fit decreasing bin-packing algorithm to maximize
        batch utilization and reduce padding waste.

        Args:
            token_counts: List of token counts per request.
            max_batch_size: Maximum requests per batch.
            max_batch_tokens: Maximum total tokens per batch.

        Returns:
            BatchSchedule with batches as lists of request indices.
        """
        if not token_counts:
            return BatchSchedule()

        # Sort by token count descending (first-fit decreasing)
        indexed = sorted(enumerate(token_counts), key=lambda x: x[1], reverse=True)

        batches: list[list[int]] = []
        batch_token_totals: list[int] = []

        for orig_idx, tokens in indexed:
            tokens = min(tokens, self.max_sequence_length)
            placed = False

            for i, batch in enumerate(batches):
                if (
                    len(batch) < max_batch_size
                    and batch_token_totals[i] + tokens <= max_batch_tokens
                ):
                    batch.append(orig_idx)
                    batch_token_totals[i] += tokens
                    placed = True
                    break

            if not placed:
                batches.append([orig_idx])
                batch_token_totals.append(tokens)

        total_tokens = sum(token_counts)
        naive_batches = math.ceil(len(token_counts) / max_batch_size)
        cost_reduction_pct = max(0.0, (1 - len(batches) / naive_batches) * 100) if naive_batches > 0 else 0.0

        throughput = (
            total_tokens / (len(batches) / (self.tokens_per_second_per_gpu / max_batch_tokens))
            if batches
            else 0.0
        )

        schedule = BatchSchedule(
            batches=batches,
            estimated_throughput=round(throughput, 2),
            cost_reduction_pct=round(cost_reduction_pct, 2),
            total_requests=len(token_counts),
            total_batches=len(batches),
        )

        logger.info(
            "batch_schedule_created",
            total_requests=schedule.total_requests,
            total_batches=schedule.total_batches,
            cost_reduction_pct=schedule.cost_reduction_pct,
        )
        return schedule

    def estimate_cost_reduction(
        self, token_counts: list[int], max_batch_size: int = 32
    ) -> float:
        """Estimate percentage cost reduction from batching vs. sequential processing."""
        schedule = self.optimize_batch_schedule(token_counts, max_batch_size)
        return schedule.cost_reduction_pct

    def try_compile_inference_graph(self, model_fn) -> Any:
        """Attempt to compile inference function with PyTorch Dynamo.

        Args:
            model_fn: PyTorch model forward function.

        Returns:
            Compiled function (or original if torch not available).
        """
        try:
            import torch
            compiled = torch.compile(model_fn, mode="reduce-overhead")
            self._dynamo_compiled = True
            logger.info("dynamo_compilation_successful")
            return compiled
        except ImportError:
            logger.warning("torch_not_available_skipping_dynamo_compilation")
            return model_fn
        except Exception as e:
            logger.warning("dynamo_compilation_failed", error=str(e))
            return model_fn
