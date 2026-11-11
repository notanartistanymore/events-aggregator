from fastapi import FastAPI

app = FastAPI()


@app.get("/api/health", status_code=200, tags=["Dev"])
def health_check():
    return {"status": "ok"}
