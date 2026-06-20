from pathlib import Path
import importlib.util
import json
import os

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel


DEFAULT_LLM_PATH = Path(__file__).resolve().parent / "llm.py"
LLM_PATH = Path(os.getenv("LLM_PATH", DEFAULT_LLM_PATH)).resolve()


def load_llm_module():
    spec = importlib.util.spec_from_file_location("llm", LLM_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {LLM_PATH}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


llm = load_llm_module()
app = FastAPI(title="Food LLM API")


# ---- warmup ---
@app.on_event("startup")
def warmup():
    print("Starting LLM warmup...")
    try:
        llm.decompose_routing("warmup")
        print("LLM warmup completed successfully.")
    except Exception as e:
        print(f"LLM warmup warning (ignored): {e}")
# --- warmup ----




from pydantic import ConfigDict, Field

class DecomposeRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    user_query: str = Field(alias="userQuery")

class AnswerRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    user_query: str = Field(alias="userQuery", default="")
    recipe_query_results: list[dict] | None = Field(alias="recipeQueryResults", default=None)
    recipe_query: dict | None = Field(alias="recipeQuery", default=None)
    results: dict | list | None = None
    user_ingredients: list[str] | None = Field(alias="userIngredients", default=None)


@app.post("/decompose")
def decompose(request: DecomposeRequest):
    try:
        json_text = llm.decompose_routing(request.user_query)
        return json.loads(json_text)
    except Exception as exc:
        err_msg = str(exc)
        if "429" in err_msg or "quota" in err_msg.lower() or "RESOURCE_EXHAUSTED" in err_msg:
            raise HTTPException(status_code=429, detail="Quota Exceeded") from exc
        raise HTTPException(status_code=500, detail=err_msg) from exc


@app.post("/answer")
def answer(request: AnswerRequest):
    try:
        req_results = request.recipe_query_results if request.recipe_query_results is not None else request.results
        
        req_ingredients = request.user_ingredients
        if req_ingredients is None and request.recipe_query:
            req_ingredients = request.recipe_query.get("user_ingredients") or request.recipe_query.get("userIngredients")

        final_answer = llm.generate_answer(
            user_query=request.user_query,
            results=req_results,
            user_ingredients=req_ingredients,
        )
        return {"answer": final_answer}
    except Exception as exc:
        err_msg = str(exc)
        if "429" in err_msg or "quota" in err_msg.lower() or "RESOURCE_EXHAUSTED" in err_msg:
            raise HTTPException(status_code=429, detail="Quota Exceeded") from exc
        raise HTTPException(status_code=500, detail=err_msg) from exc
