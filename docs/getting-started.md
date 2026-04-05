# Getting Started

## Prerequisites

- Python 3.10+
- Redis (optional for development)
- PostgreSQL (optional for development)
- Anthropic API key or OpenAI API key

## Installation

```bash
# 1. Clone
git clone https://github.com/your-org/agent-inference-stack.git
cd agent-inference-stack

# 2. Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
```

## Configuration

Edit `.env` and set at minimum:
```bash
ANTHROPIC_API_KEY=your_anthropic_api_key_here
# OR
OPENAI_API_KEY=your_openai_api_key_here
```

## Running the API

```bash
make dev
# OR
uvicorn src.api.app:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

## First Request

```bash
curl -X POST http://localhost:8000/api/v1/process \
  -H "Content-Type: application/json" \
  -d '{
    "request": "Research the top 5 CRM software companies, their pricing and key features",
    "context": {"industry": "B2B SaaS"}
  }'
```

Response:
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending",
  "message": "Request accepted for processing"
}
```

## Checking Status

```bash
curl http://localhost:8000/api/v1/status/550e8400-e29b-41d4-a716-446655440000
```

## Running with Docker

```bash
# Start all services (API + Redis + PostgreSQL)
make docker-up

# View logs
make docker-logs

# Stop
make docker-down
```

## Running Tests

```bash
# All tests
make test

# Unit tests only (no external services needed)
make test-unit

# With coverage report
pytest tests/ --cov=src --cov-report=html
```

## Troubleshooting

**"Orchestrator not initialized"** — Check that your API key is set in `.env`

**LLM calls failing** — Verify `ANTHROPIC_API_KEY` is valid and has quota

**Redis connection errors** — The app works without Redis in development (state kept in-memory)

**Import errors** — Ensure you're in the virtual environment: `source .venv/bin/activate`
