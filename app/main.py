from fastapi import FastAPI

from app.api.routes import reports

app = FastAPI(
    title="PDF Report Generator API",
    description="API for generating PDF reports asynchronously",
    version="1.0.0",
)

app.include_router(reports)


@app.get("/")
def root():
    return {"message": "PDF Report Generator API is running"}


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "pdf-report-generator"
    }