import os
from langgraph.types import Command
from langchain_core.messages import AIMessage
from dotenv import load_dotenv
from agent import app
import warnings
warnings.filterwarnings("ignore")

 
load_dotenv()
os.environ["LANGCHAIN_TRACING_V2"] = "true"
os.environ["LANGCHAIN_PROJECT"] = "PA_CallCenter_Agent"

def run_chat():
    config = {"configurable": {"thread_id": "call_1"}}
    
    print("\n[System]: Starting PA Call Center Stream...\n")
    
    # 1. Initial Stream (Runs 'start_node' and hits first 'interrupt')
    for event in app.stream({"messages": []}, config):
        if "__interrupt__" in event:
            continue
        for node_name, state_update in event.items():
            if "messages" in state_update and state_update["messages"]:
                last_msg = state_update["messages"][-1]
                if isinstance(last_msg, AIMessage):
                    print(f"Agent: {last_msg.content}")

    # 2. Continuous Chat Loop relying on Command(resume=...)
    while True:
        state = app.get_state(config)
        if not state.next:
            break # The graph has reached 'END'
            
        user_input = input("Provider: ")
        
        # Resume the interrupted node with user input
        for event in app.stream(Command(resume=user_input), config):
            if "__interrupt__" in event:
                continue
            for node_name, state_update in event.items():
                if "messages" in state_update and state_update["messages"]:
                    last_msg = state_update["messages"][-1]
                    # Print only the AI's response to keep output clean
                    if isinstance(last_msg, AIMessage):
                        print(f"Agent ({node_name}): {last_msg.content}")

if __name__ == "__main__":
    run_chat()