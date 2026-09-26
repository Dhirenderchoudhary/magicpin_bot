import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional

from .bot import compose
from .models import ComposeInput, ComposeOutput

app = FastAPI(title="MagicPin Vera Bot", version="1.0")

@app.get("/health")
def health_check():
    """Render health check – returns 200 OK."""
    return {"status": "ok"}


class ComposeRequest(BaseModel):
    category: dict
    merchant: dict
    trigger: dict
    customer: Optional[dict] = None

class ComposeResponse(BaseModel):
    body: str
    cta: str
    send_as: str
    suppression_key: str
    rationale: str

@app.post("/compose", response_model=ComposeResponse)
def compose_endpoint(request: ComposeRequest):
    try:
        result = compose(
            category=request.category,
            merchant=request.merchant,
            trigger=request.trigger,
            customer=request.customer,
        )
        # result is a dict matching ComposeOutput
        return ComposeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
