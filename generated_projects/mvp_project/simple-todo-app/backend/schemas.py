from pydantic import BaseModel

class TaskCreate(BaseModel):
    title: str
    description: str = None

class TaskUpdate(BaseModel):
    title: str = None
    description: str = None
    completed: bool = None

class Task(BaseModel):
    id: int
    title: str
    description: str = None
    completed: bool = False

    class Config:
        orm_mode = True