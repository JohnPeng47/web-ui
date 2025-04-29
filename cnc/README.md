# Pentest Hub

A hub-and-spoke FastAPI service for pentest traffic collection and analysis.

## Overview

This application:
1. Receives traffic crawled by independent browser agents
2. Stores it in a SQLite database
3. Fans out that traffic to enrichment workers
4. Fans in the enriched stream to attack workers (starting with AuthzAttacker)

The system is 100% async, with in-memory queues and SQLite persistence behind a repository pattern.

## Architecture

### Components

- **API Layer**: FastAPI routers handle HTTP requests, validate inputs, and manage dependencies.
- **Service Layer**: Contains the business logic, orchestrates database operations, and manages async queues.
- **Database Layer**: Models, CRUD operations, and session management using SQLModel/SQLAlchemy.
- **Helpers**: Utilities for queue management, UUID generation, etc.
- **Workers**: Async tasks that subscribe to queues, process data, and republish to other queues.

### Workflow

1. Browser agents register with an application
2. Agents push HTTP messages (requests/responses) to the API
3. Messages are stored in the database and published to the `raw_http_msgs` queue
4. The enrichment worker reads from the queue, analyzes messages, and publishes enriched data
5. Attack workers (like AuthzAttacker) read enriched data and detect potential vulnerabilities

## Setup

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd pentest-hub

# Install dependencies
pip install -r requirements.txt
```

### Running the Application

Start the API server:

```bash
python main.py
```

Start the workers:

```bash
python workers_launcher.py
```

## Usage

### Creating an Application

```bash
curl -X POST "http://localhost:8000/application/" \
     -H "Content-Type: application/json" \
     -d '{"name": "My Web App", "description": "Web application for testing"}'
```

### Registering an Agent

```bash
curl -X POST "http://localhost:8000/application/{app_id}/agents/register" \
     -H "Content-Type: application/json" \
     -d '{"user_name": "test_agent", "role": "admin"}'
```

### Pushing HTTP Messages

```bash
curl -X POST "http://localhost:8000/application/{app_id}/agents/push" \
     -H "Content-Type: application/json" \
     -H "X-Username: test_agent" \
     -H "X-Role: admin" \
     -d '{"messages": [{
         "request": {
             "method": "GET",
             "url": "https://example.com/api/users/123",
             "headers": {"User-Agent": "Mozilla/5.0"},
             "is_iframe": false
         },
         "response": {
             "url": "https://example.com/api/users/123",
             "status": 200,
             "headers": {"Content-Type": "application/json"},
             "is_iframe": false
         }
     }]}'
```

## Testing

Run tests with pytest:

```bash
pytest
```

## Development

The project follows a clean architecture with separation of concerns:

- `routers/`: API endpoints
- `services/`: Business logic
- `database/`: Data persistence
- `schemas/`: Data validation
- `workers/`: Async processing
- `helpers/`: Utilities
- `tests/`: Test suite