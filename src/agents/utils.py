from langchain_core.messages import AIMessage, HumanMessage


def format_history(messages: list) -> str:
    formated_history = []
    for message in messages:
        if isinstance(message, HumanMessage):
            formated_history.append(f"User: {message.content}")
        elif isinstance(message, AIMessage):
            formated_history.append(f"Assistant: {message.content}")
    return "\n".join(formated_history)
