from celery import Celery

from src.agents.ci_agent import CIAgent

app = Celery(
    "tasks",
    broker="redis://localhost:6379",
    backend="redis://localhost:6379",
)

ci_agent = CIAgent()

@app.task
def process_chat_task(prompt):
    try:
        agent_reply = ci_agent.generate_reply(query=prompt)
        answer = agent_reply.get("answer", "")
        return {"answer": answer}
    except Exception as e:
        return {"error": str(e)}
