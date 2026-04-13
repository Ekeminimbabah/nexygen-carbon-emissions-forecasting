from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import statsmodels.api as sm
from contextlib import asynccontextmanager
import pandas as pd
from typing import Literal

models = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    models['scope1'] = sm.load('scope1_model.pkl')
    models['scope2'] = sm.load('scope2_model.pkl')
    print("Models loaded successfully.")
    
    yield  # This is where the application will run
    models.clear()  # Clear the models from memory on shutdown
    # Cleanup code can go here if needed (e.g., closing database connections)


app = FastAPI(
    lifespan=lifespan,
    title="Carbon Emissions Forecasting API",
    description="API for forecasting Nexigen carbon emissions based on Scope 1 and Scope 2 data.",
    version="1.0.0"
    
    )

# Define a structure/validation for our request and response models

class ForecastRequest(BaseModel):
    emission_type: Literal['scope1', 'scope2']
    steps: int


class ForecastResponse(BaseModel):
    emission_type: str
    forecast: list[float]
    dates: list[str]

@app.get("/")
def health():
    return {"status": "ok",
        "service": "Nexigen Carbon Emissions Forecasting API is running."}

@app.post("/forecast", response_model=ForecastResponse)
def forecast(request: ForecastRequest):
    key = 'scope1' if request.emission_type == 'scope1' else 'scope2'
    model = models.get(key)
    if not model:
        raise HTTPException(status_code=500, detail="Model not loaded.")
    
    pred = model.forecast(steps=request.steps)
    print(pred)
    print(pred.index)

    return ForecastResponse(
        emission_type=request.emission_type,
        forecast=[float(v) for v in pred.tolist()],
        dates= [str(d) for d in pred.index.to_list()]
    )