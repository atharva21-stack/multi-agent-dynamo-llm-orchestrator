# Architecture

## System Overview

agent-inference-stack implements a multi-agent AI pipeline with four specialized agents
coordinated by a central orchestrator.

## Components

### 1. API Gateway (`src/api/`)
FastAPI application exposing REST endpoints. Handles:
- Request validation (Pydantic)
- Request ID injection
- Structured logging per request
- CORS configuration
- Health/metrics endpoints

### 2. Orchestrator (`src/orchestration/`)
Central coordinator that manages the full request lifecycle:
1. **Planning Phase** — calls PlanningAgent to decompose request into tasks
2. **Execution Phase** — resolves DAG dependencies, executes task waves in parallel
3. **Validation Phase** — calls ValidationAgent on final output

Key classes:
- `Orchestrator` — top-level coordinator
- `DependencyResolver` — topological sort (Kahn's algorithm)
- `TaskExecutor` — routes tasks to agents

### 3. Agents (`src/agents/`)

| Agent | Model | Responsibility |
|-------|-------|---------------|
| PlanningAgent | claude-sonnet-4-6 | Break request into tasks with dependencies |
| ResearchAgent | claude-haiku-4-5-20251001 | Search + synthesize information |
| ExecutionAgent | claude-sonnet-4-6 | Perform task using tools |
| ValidationAgent | claude-haiku-4-5-20251001 | Quality-score the output |

All agents extend `BaseAgent` which provides:
- Exponential backoff retry logic
- Token counting and cost tracking
- Unified LLM interface (Anthropic/OpenAI/vLLM)
- Structured logging with agent context

### 4. Inference Engine (`src/inference/`)
- `vLLMEngine` — connects to vLLM server (HTTP), falls back to Anthropic API
- `DynamoOptimizer` — bin-packing for efficient GPU batching
- `InferenceCache` — Redis-backed prompt/response cache

### 5. Storage (`src/storage/`)
- `RedisClient` — async connection pool, JSON serialization, hot state cache
- `PostgreSQLClient` — asyncpg pool, schema creation, audit trail
- SQLAlchemy ORM models for persistence

### 6. Monitoring (`src/monitoring/`)
- Prometheus metrics (counters, histograms, gauges)
- Structured JSON logging via structlog
- Health check functions per dependency

## Data Flow

```
1. Client → POST /api/v1/process
2. Orchestrator.submit_request() → creates ExecutionRequest, starts background task
3. PlanningAgent.execute() → JSON plan with Task DAG
4. DependencyResolver.topological_sort() → execution waves
5. For each wave (parallel): TaskExecutor.execute_task() → agent.execute()
6. ValidationAgent.execute() → ValidationResult
7. Client polls GET /api/v1/status/{id} until completed
```

## Design Decisions

**Why DAG-based scheduling?**
Tasks often have data dependencies (e.g., synthesis requires research results).
A DAG ensures correct execution order while maximizing parallelism.

**Why Dynamo token batching?**
GPU inference is much more efficient when requests with similar token lengths
are batched together. Dynamo's first-fit decreasing algorithm reduces GPU idle time.

**Why disaggregated prefill/decode?**
Prefill (prompt processing) is compute-bound; decode (token generation) is memory-bound.
Routing them to different GPU types (H100/B100) optimizes hardware utilization.
