# SmartVal MCP – AI shopping agent for SmartValGuiden.se

An **agentic AI** prototype for [SmartValGuiden.se](https://smartvalguiden.se), my Swedish electronics comparison site.
A locally hosted LLM (via **Ollama**) answers buying questions such as *"Which laptop under 10 000 kr is best for programming?"*.
It does this by calling tools exposed through a **Model Context Protocol (MCP)** server, which in turn queries a
**REST API** over the product catalogue. All parts are **containerised with Docker** and can be deployed to **Kubernetes**.

```
 ┌──────────────┐   tool calls    ┌──────────────┐   HTTP/JSON   ┌──────────────┐
 │  AI agent    │ ──── MCP ─────▶ │  MCP server  │ ────────────▶ │  REST API    │
 │ Ollama LLM   │ ◀── results ─── │  (5 tools)   │ ◀──────────── │  FastAPI     │
 │ (qwen3)      │                 └──────────────┘               │  BM25 search │
 └──────────────┘                                                │  products.json│
                                                                 └──────────────┘
```

## What it shows

| Area | Implementation |
|---|---|
| **AI agents / agentic workflow** | `smartval/agent.py` – tool-calling loop: the LLM picks tools, gets JSON results back and iterates until it can give a grounded answer |
| **MCP** | `smartval/mcp_server.py` – MCP server (official Python SDK) with `search_products`, `list_products`, `get_product`, `compare_products`, `list_categories`; stdio and streamable-HTTP transports |
| **RAG** | Retrieval step uses a BM25 ranker (`smartval/retrieval.py`); the LLM answers only from retrieved product data |
| **REST API** | `smartval/api.py` – FastAPI with filtering, sorting, search and side-by-side comparison; OpenAPI docs at `/docs` |
| **Data validation** | Pydantic schemas validate every product on load (types, price ≥ 0, rating 0–5, unique ids) |
| **Containers / cloud-native** | `Dockerfile` (non-root), `docker-compose.yml` (API + MCP + Ollama), Kubernetes manifests in `k8s/` with probes and resource limits |
| **Testing / CI** | 13 pytest tests (API, retrieval, MCP tools in-process, agent loop with a scripted LLM); GitHub Actions runs the tests, builds the image and smoke-tests the container |

## Quick start (local)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest

# 1. REST API  → http://localhost:8000/docs
uvicorn smartval.api:app --reload

# 2. Ask the agent (needs Ollama running: https://ollama.com)
ollama pull qwen3:8b
python -m smartval.agent -v "Vilken laptop under 10 000 kr passar bäst för programmering?"
```

The agent starts the MCP server over stdio automatically. Use `--model` to choose another Ollama model
with tool-calling support (e.g. `qwen2.5-coder:7b`).

### Use the MCP server from another client (e.g. Claude Desktop, VS Code)

```json
{
  "mcpServers": {
    "smartval": {
      "command": "python",
      "args": ["-m", "smartval.mcp_server"],
      "env": { "SMARTVAL_API_URL": "http://localhost:8000" }
    }
  }
}
```

## Docker

```bash
docker compose up --build          # API on :8000, MCP (HTTP) on :8001/mcp, Ollama on :11434
docker compose exec ollama ollama pull qwen3:8b
SMARTVAL_MCP_URL=http://localhost:8001/mcp python -m smartval.agent "Bästa brusreducerande hörlurar?"
```

## Kubernetes (minikube)

```bash
minikube start
minikube image build -t smartval-mcp:0.1.0 .
kubectl apply -f k8s/
kubectl get pods
kubectl port-forward svc/smartval-api 8000:8000
```

## API endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check (used by Docker and Kubernetes probes) |
| GET | `/categories` | All categories |
| GET | `/products?category=&brand=&min_price=&max_price=&sort=` | Filtered product list |
| GET | `/products/{id}` | One product |
| GET | `/search?q=&category=&max_price=&limit=` | BM25 free-text search (Swedish/English, accent-insensitive) |
| GET | `/compare?ids=a,b` | Side-by-side spec table, cheapest and highest rated |

## Project structure

```
smartval/
  api.py          REST API (FastAPI + Pydantic)
  retrieval.py    BM25 retriever (no external dependencies)
  mcp_server.py   MCP server exposing the API as tools
  agent.py        Ollama tool-calling agent (MCP client)
data/products.json  Sample catalogue
tests/          pytest suite
k8s/            Kubernetes deployments and services
```

## Notes

- `data/products.json` is **sample data** with approximate prices, made for this prototype – not live prices from SmartValGuiden.se.
- Next steps: embedding-based semantic search with Ollama embeddings, connecting to the live SmartValGuiden database, and an evaluation set for answer quality.

## License

MIT
