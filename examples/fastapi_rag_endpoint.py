from fastapi import FastAPI
from pydantic import BaseModel


app = FastAPI()


class QueryRequest(BaseModel):
    question: str


@app.post("/query")
def query(request: QueryRequest):
    return {
        "answer": "Refunds are available within 30 days of purchase.",
        "contexts": [
            {
                "id": "refund_policy_1",
                "text": "Customers may request a refund within 30 days of purchase when the product has not been consumed.",
                "source": "refund_policy.md",
                "score": 0.92,
            }
        ],
        "citations": [
            {
                "claim": "Refunds are available within 30 days of purchase.",
                "source_chunk_id": "refund_policy_1",
            }
        ],
        "usage": {"total_tokens": 96},
        "model": "demo-rag",
    }
