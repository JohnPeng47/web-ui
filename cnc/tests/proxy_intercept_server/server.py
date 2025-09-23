from pathlib import Path
import json

from fastapi import FastAPI
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="Proxy Intercept Test Server")

# Serve the current folder as static, in case you add assets later.
app.mount("/static", StaticFiles(directory=str(BASE_DIR)), name="static")


@app.get("/")
def get_index() -> FileResponse:
    return FileResponse(str(BASE_DIR / "index.html"))


@app.get("/api/data")
def get_api_data() -> Response:
    # Intentionally return 304 with a JSON body to exercise proxy/interceptor behavior.
    # Some clients may ignore bodies on 304 by spec, so also mirror JSON in X-JSON header.
    payload = {"message": "Hello from 304", "ok": True}
    body = json.dumps(payload)
    body_bytes = body.encode("utf-8")
    return Response(content=body_bytes, status_code=200)

if __name__ == "__main__":
    # Run with: python server.py [port]
    import uvicorn
    import sys

    port = 8005
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            print(f"Invalid port number: {sys.argv[1]}")
            sys.exit(1)

    uvicorn.run("server:app", host="127.0.0.1", port=port, reload=False)
