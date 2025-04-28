# Pentest Hub

A FastAPI-based "central command" that coordinates pentesting browser agents, processes the traffic they produce, enriches it, and drives attack workers.

## Features

- REST API using FastAPI
- In-process thread-safe queues for message passing
- Dynamic worker registration for extensibility
- PostgreSQL for state persistence
- Background workers for enrichment and attack processes

## Architecture

### Core Components

- **Protocol**: Common data contracts (HTTPRequestData, ResourceLocator, AttackData)
- **EventBus**: Thread-safe in-process queue for message passing
- **Enrichers**: Analyze raw requests and extract resource locators
- **Attack Workers**: Process enriched data to check for vulnerabilities

### Design Choices

- **North-bound API**: FastAPI (REST)
- **Queue/Bus**: In-process asyncio.Queue with thread-safe wrapper
- **Worker Execution**: ThreadPoolExecutor (keeps GIL impact low)
- **Plugin Mechanism**: Via registry system (future: importlib.metadata entry-points)
- **State Store**: PostgreSQL
- **Observability**: Structured logging with OpenTelemetry stubs

## Getting Started

### Prerequisites

- Python 3.9+
- PostgreSQL database

### Installation

1. Clone the repository
2. Create a virtual environment: `python -m venv venv`
3. Activate the environment: `source venv/bin/activate` (Linux/macOS) or `venv\Scripts\activate` (Windows)
4. Install dependencies: `pip install -e .`
5. Create a `.env` file with configuration (see `.env.example`)

### Running the Application

1. Start the API server: `uvicorn app.main:app --reload`
2. Start the worker process: `python worker_entry.py`

## Development

### Running Tests

```bash
pytest              # Run all tests
pytest -v           # Verbose output
pytest -xvs         # Very verbose output, show stdout
pytest app/tests/unit/test_pipeline.py  # Run specific test file
```

### Project Structure

```
pentest-hub/
├─ app/
│  ├─ main.py              # FastAPI bootstrap
│  ├─ api/                 # REST routes & Pydantic schemas
│  ├─ core/                # Configuration, logging, registry
│  ├─ domain/              # ORM models and DTOs
│  ├─ protocol/            # Common DTOs
│  ├─ services/            # Core services
│  ├─ workers/             # Enrichers and attackers
│  └─ tests/               # Unit and integration tests
└─ worker_entry.py         # Worker process entry point
```

## License

[MIT License](LICENSE)