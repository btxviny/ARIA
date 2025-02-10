from fastapi import FastAPI
from pydantic import BaseModel
from celery.result import AsyncResult
from src.tasks import process_chat_task, app as celery_app

app = FastAPI()

print( """
   _____ _____                 _____ ______ _   _ _______                _____ _____ 
  / ____|_   _|          /\   / ____|  ____| \ | |__   __|         /\   |  __ \_   _|
 | |      | |    ______ /  \ | |  __| |__  |  \| |  | |______     /  \  | |__) || |  
 | |      | |   |______/ /\ \| | |_ |  __| | . ` |  | |______|   / /\ \ |  ___/ | |  
 | |____ _| |_        / ____ \ |__| | |____| |\  |  | |         / ____ \| |    _| |_ 
  \_____|_____|      /_/    \_\_____|______|_| \_|  |_|        /_/    \_\_|   |_____|                                                                                                                      
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

