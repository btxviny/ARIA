from celery import Celery

from src.agents.ci_agent import CIAgent

# Initialize Celery app
app = Celery(
    "tasks",
    broker="redis://localhost:6379",  # Redis broker URL
    backend="redis://localhost:6379",  # Redis backend URL
)

ci_agent = CIAgent()

@app.task
def process_chat_task(prompt):
    try:
        agent_reply = ci_agent.generate_reply(query = prompt)
        answer = agent_reply.get("answer", [])
        generated_file = agent_reply.get("generated_file", "")
        return {"answer": answer, "generated_file": generated_file}
    except Exception as e:
        return {"error": str(e)}
