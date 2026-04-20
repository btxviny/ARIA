from dotenv import load_dotenv
from time import time
from src.agents.graph import app
from loguru import logger
load_dotenv()


config = {"configurable": {"thread_id": "1"}}

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

def main():
    logger.info("System is ready for user queries.")
    while True:
        query = input("Your question: ")
        if query.lower() == 'exit':
            logger.info("User terminated the session.")
            break
        inputs = {"question": query, "executed_agents": []}
        for event in app.stream(inputs, config, stream_mode="values"):
            pass
        logger.info(f"Final state: {event}")
        final_answer = event.get("messages",[{}])[-1].content
        logger.success(f"Final response: {final_answer}")

if __name__ == "__main__":
    main()
    