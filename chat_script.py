from dotenv import load_dotenv
from time import time
from src.agents.graph import app
from loguru import logger
import sys
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
    
    # Check if query was passed as command-line argument
    if len(sys.argv) > 1:
        query = " ".join(sys.argv[1:])
        logger.info(f"Query from command-line argument: {query}")
        process_query(query)
    else:
        # Interactive mode
        while True:
            query = input("Your question: ")
            if query.lower() == 'exit':
                logger.info("User terminated the session.")
                break
            process_query(query)

def process_query(query: str):
    """Process a single query through the agent graph."""
    inputs = {"question": query, "executed_agents": []}
    for event in app.stream(inputs, config, stream_mode="values"):
        pass
    logger.info(f"Final state: {event}")
    final_answer = event.get("messages",[{}])[-1].content
    logger.success(f"Final response: {final_answer}")

if __name__ == "__main__":
    main()