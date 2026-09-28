from fastapi import FastAPI


app = FastAPI(title="Hairly API")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

