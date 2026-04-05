# API Reference

Base URL: `http://localhost:8000/api/v1`

## Endpoints

### POST /process

Submit a request for multi-agent processing.

**Request Body:**
```json
{
  "request": "string (10-10000 chars, required)",
  "context": {"key": "value"},
  "priority": 1,
  "max_tokens": null,
  "timeout_seconds": null
}
```

**Response (202 Accepted):**
```json
{
  "request_id": "uuid",
  "status": "pending",
  "message": "Request accepted for processing",
  "estimated_tokens": 5000,
  "estimated_cost_usd": 0.075
}
```

---

### GET /status/{request_id}

Check processing status.

**Response (200 OK):**
```json
{
  "request_id": "uuid",
  "status": "completed",
  "result": {...},
  "agent_results": [
    {
      "agent_type": "planning",
      "status": "completed",
      "tokens_used": 1200,
      "cost_usd": 0.018,
      "latency_ms": 2150.0
    }
  ],
  "total_tokens": 4823,
  "total_cost_usd": 0.072,
  "duration_ms": 12500.0
}
```

**Status values:** `pending | planning | executing | validating | completed | failed`

---

### GET /metrics

System performance metrics.

**Response (200 OK):**
```json
{
  "total_requests": 1523,
  "successful_requests": 1498,
  "failed_requests": 25,
  "avg_latency_ms": 8750.0,
  "p95_latency_ms": 22000.0,
  "total_tokens": 7650000,
  "total_cost_usd": 229.50
}
```

---

### GET /health

Service health check.

**Response (200 OK):**
```json
{
  "status": "healthy",
  "version": "0.1.0",
  "environment": "production",
  "dependencies": [
    {"name": "redis", "status": "healthy", "latency_ms": 1.2},
    {"name": "orchestrator", "status": "healthy"}
  ]
}
```

## Error Codes

| Code | Meaning |
|------|---------|
| 202 | Request accepted |
| 400 | Bad request |
| 404 | Request ID not found |
| 422 | Validation error |
| 500 | Internal server error |
| 503 | Service unavailable |
