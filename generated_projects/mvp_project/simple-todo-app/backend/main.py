from fastapi import FastAPI, HTTPException
from routers import tasks

app = FastAPI()

app.include_router(tasks.router)

@app.get("/")
async def read_root():
    return {"message": "Welcome to the Simple Todo App"}