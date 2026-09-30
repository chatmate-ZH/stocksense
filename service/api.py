"""StockSense scoring service.  Run: uvicorn service.api:app --reload   Docs: /docs"""
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from src.scoring import score_sku, _q

app = FastAPI(title="StockSense Scoring API", description="6-week demand forecast + stockout/overstock risk for any product.")

class StockOverride(BaseModel):
    on_hand: Optional[int] = Field(None, ge=0, description="Units in warehouse now")
    on_order: Optional[int] = Field(None, ge=0, description="Units ordered, not yet received")
    lead_days: Optional[int] = Field(None, ge=1, le=120, description="Days for a new order to arrive")

class Batch(BaseModel):
    sku_ids: List[str] = Field(..., min_length=1, max_length=50)

@app.get("/")
def health(): return {"status": "ok", "try": "/docs"}

@app.get("/skus")
def skus(): return _q("select sku_id, product_name, category from sku_master").to_dict("records")

@app.get("/score/{sku_id}")
def score(sku_id: str, on_hand: Optional[int] = None, on_order: Optional[int] = None, lead_days: Optional[int] = None):
    """Forecast + risk for one product. Optional stock numbers give a what-if answer."""
    if any(v is not None and v < 0 for v in (on_hand, on_order, lead_days)): raise HTTPException(422, "Stock numbers cannot be negative.")
    try: return score_sku(sku_id.upper(), on_hand, on_order, lead_days)
    except KeyError: raise HTTPException(404, f"Unknown sku_id '{sku_id}'. See /skus for valid ids.")

@app.post("/score/batch")
def batch(b: Batch):
    ok, missing = [], []
    for s in b.sku_ids:
        try: ok.append(score_sku(s.upper()))
        except KeyError: missing.append(s)
    return {"results": ok, "not_found": missing}
