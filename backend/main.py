from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def root():
    return {"message": "Resilience Board API running"}

@app.get("/health")
def health():
    return {"status": "healthy"}
