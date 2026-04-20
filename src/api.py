from fastapi import FastAPI
from pydantic import BaseModel
from celery.result import AsyncResult
from src.tasks import process_chat_task, app as celery_app

app = FastAPI()

print(r"""
  __  __       _ _   _          _                    _   
 |  \/  |     | | | (_)   /\   | |                  | |  
 | \  / |_   _| | |_ _   /  \  | | __ _  ___ _ __ | |_ 
 | |\/| | | | | | __| | / /\ \ | |/ _` |/ _ \ '_ \| __|
 | |  | | |_| | | |_| |/ ____ \| | (_| |  __/ | | | |_ 
 |_|  |_|\__,_|_|\__|_/_/    \_\_|\__, |\___|_| |_|\__|
                                    __/ |               
                                   |___/                
""")

# Define the request body model
class ChatRequest(BaseModel):
    prompt: str

@app.post("/question/")
def question(request: ChatRequest):
    # Trigger the Celery task with the body data
    task = process_chat_task.apply_async(args=[request.prompt])
    return {"task_id": task.id}

@app.get("/answer/{task_id}")
def answer(task_id: str):
    # Fetch the result of the task
    task_state = AsyncResult(task_id, app=celery_app).state

    if task_state == "PENDING":
        return {"status": "Task is still running"}
    elif task_state == "SUCCESS":   
        return {"status": "Completed", "result": AsyncResult(task_id, app=celery_app).get()}
    else:
        return {"status": "Failed", "error": AsyncResult(task_id, app=celery_app).get()}

