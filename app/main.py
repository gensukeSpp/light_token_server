from fastapi import FastAPI

app = FastAPI(title="light-token-server")


@app.get("/health")
def health():
    return {"status": "ok"}