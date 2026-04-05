# Multi Agent Dynamo LLM Orchestrator

A production-ready multi-agent AI system with **Dynamo token batching**, **vLLM inference**, and **Kubernetes orchestration**.

## Architecture

```
                     User Request                              
                          ▼
 ┌─────────────────────────────────────────────────────────┐
 │                   FastAPI Gateway                       │
 │              POST /api/v1/process                       │
 └─────────────────────┬───────────────────────────────────┘
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   Orchestrator                          │
│  ┌───────────┐  ┌─────────────┐  ┌──────────────────┐   │
│  │ Planning  │→ │  Execution  │→ │   Validation     │   │
│  │  Agent    │  │  Pipeline   │  │    Agent         │   │
│  └───────────┘  └──────┬──────┘  └──────────────────┘   │
│                        │                                │
│               ┌────────┼─────────┐                      │
│               ▼        ▼         ▼                      │
│          Research  Execution  Validation                │
│          Agents     Agents     Agents                   │
└─────────────────────────────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
     vLLM Engine    Redis DB    PostgreSQL
  (Dynamo Batched)  (State)    (Persistence)
```

## Key Features

- **Multi-Agent Pipeline**: Planning → Research → Execution → Validation
- **DAG-based Scheduling**: Parallel task execution with dependency resolution
- **Dynamo Token Batching**: First-fit decreasing bin-packing for GPU efficiency
- **vLLM Integration**: High-throughput inference with paged attention
- **Disaggregated Inference**: Prefill on Hopper (H100), decode on Blackwell (B100)
- **Cost Tracking**: Per-request token and USD cost tracking
- **Production-Ready**: Redis caching, PostgreSQL persistence, Prometheus metrics

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/your-org/agent-inference-stack.git
cd agent-inference-stack
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run development server
make dev

# 4. Test the API
curl -X POST http://localhost:8000/api/v1/process \
  -H "Content-Type: application/json" \
  -d '{"request": "Research the top 5 CRM software companies and compare their features"}'
```

## Documentation

- [Architecture](docs/architecture.md)
- [Getting Started](docs/getting-started.md)
- [API Reference](docs/api-reference.md)
- [Deployment](docs/deployment.md)
- [Configuration](docs/configuration.md)

## Tech Stack

| Component | Technology |
|-----------|-----------|
| API | FastAPI + uvicorn |
| Agents | Python async/await + Anthropic/OpenAI |
| Orchestration | Custom DAG scheduler |
| Inference | vLLM + PyTorch Dynamo |
| Cache | Redis 7 |
| Database | PostgreSQL 15 |
| Monitoring | Prometheus + structlog |
| Containers | Docker + Kubernetes |

## License

MIT License — see [LICENSE](LICENSE)
