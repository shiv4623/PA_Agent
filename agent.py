import json
from pathlib import Path
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.types import interrupt
import os
from dotenv import load_dotenv
import warnings
warnings.filterwarnings("ignore")


from state import (
    AgentState, ProviderOutput, PatientOutput, AuthOutput, LookupOutput, EndOutput
)

load_dotenv()

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY", "")
AZURE_OPENAI_DEPLOYMENT = os.getenv("AZURE_OPENAI_DEPLOYMENT", "")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "")

# Initialize LLM
llm = AzureChatOpenAI(
    azure_deployment=AZURE_OPENAI_DEPLOYMENT,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_key=AZURE_OPENAI_API_KEY,
    temperature=0.0)

# Helper to load Jinja2 prompts
def load_prompt(file_name: str) -> ChatPromptTemplate:
    path = Path(f"prompts/{file_name}")
    content = path.read_text(encoding="utf-8")
    return ChatPromptTemplate.from_template(content, template_format="jinja2")

system_prompt_content = Path("prompts/system.md").read_text()

# --- Node Definitions ---

def start_node(state: AgentState):
    """Initiates conversation (First message must be from agent)."""
    ai_msg = "Thanks for calling. Can I get your name and a good call back number?"
    return {
        "messages": [AIMessage(content=ai_msg)],
        "next_node": "provider_intake"
    }

def provider_intake_node(state: AgentState):
    user_input = interrupt("Waiting for provider info")
    
    prompt = load_prompt("provider_intake.md").invoke({
        "provider_name": state.get("provider_name", "None"),
        "provider_callback": state.get("provider_callback", "None")
    })
    
    structured_llm = llm.with_structured_output(ProviderOutput)
    messages = [SystemMessage(content=system_prompt_content)] + state["messages"] + [HumanMessage(content=user_input)]
    messages.append(SystemMessage(content=prompt.to_string()))
    
    response = structured_llm.invoke(messages)
    
    return {
        "messages": [HumanMessage(content=user_input), AIMessage(content=response.ai_response)],
        "provider_name": response.provider_name or state.get("provider_name"),
        "provider_callback": response.provider_callback or state.get("provider_callback"),
        "next_node": response.next_node
    }

def patient_intake_node(state: AgentState):
    user_input = interrupt("Waiting for patient info")
    
    prompt = load_prompt("patient_intake.md").invoke({
        "patient_name": state.get("patient_name", "None"),
        "patient_dob": state.get("patient_dob", "None"),
        "member_id": state.get("member_id", "None")
    })
    
    structured_llm = llm.with_structured_output(PatientOutput)
    messages = [SystemMessage(content=system_prompt_content)] + state["messages"] + [HumanMessage(content=user_input)]
    messages.append(SystemMessage(content=prompt.to_string()))
    
    response = structured_llm.invoke(messages)
    
    return {
        "messages": [HumanMessage(content=user_input), AIMessage(content=response.ai_response)],
        "patient_name": response.patient_name or state.get("patient_name"),
        "patient_dob": response.patient_dob or state.get("patient_dob"),
        "member_id": response.member_id or state.get("member_id"),
        "next_node": response.next_node
    }

def auth_intake_node(state: AgentState):
    user_input = interrupt("Waiting for auth info")
    
    prompt = load_prompt("auth_intake.md").invoke({
        "auth_id": state.get("auth_id", "None"),
        "procedure": state.get("procedure", "None")
    })
    
    structured_llm = llm.with_structured_output(AuthOutput)
    messages = [SystemMessage(content=system_prompt_content)] + state["messages"] + [HumanMessage(content=user_input)]
    messages.append(SystemMessage(content=prompt.to_string()))
    
    response = structured_llm.invoke(messages)
    
    return {
        "messages": [HumanMessage(content=user_input), AIMessage(content=response.ai_response)],
        "auth_id": response.auth_id or state.get("auth_id"),
        "procedure": response.procedure or state.get("procedure"),
        "next_node": response.next_node
    }

def lookup_node(state: AgentState):
    # No interrupt here; the agent just processes the backend call
    with open("data.json", "r") as f:
        db = json.load(f)
    
    patient_match = next((p for p in db["patients"] if p["member_id"] == state.get("member_id")), None)
    
    lookup_result = "No patient found matching that Member ID."
    if patient_match:
        auth_match = None
        for a in db["authorizations"]:
            auth_id_match = state.get("auth_id") and state["auth_id"] == a["auth_id"]
            proc_match = state.get("procedure") and state["procedure"].lower() in a["procedure"].lower()
            if auth_id_match or proc_match:
                auth_match = a
                break
        
        if auth_match:
            lookup_result = f"Record Found - Procedure: {auth_match['procedure']}, Status: {auth_match['status']}. Valid/Deadline: {auth_match.get('approved_dates', auth_match.get('decision_deadline'))}"
        else:
            lookup_result = "Patient verified, but no matching authorization or procedure found."

    prompt = load_prompt("lookup.md").invoke({"lookup_result": lookup_result})
    
    structured_llm = llm.with_structured_output(LookupOutput)
    messages = [SystemMessage(content=system_prompt_content)] + state["messages"]
    messages.append(SystemMessage(content=prompt.to_string()))
    
    response = structured_llm.invoke(messages)
    
    return {
        "messages": [AIMessage(content=response.ai_response)],
        "next_node": response.next_node
    }

def end_call_node(state: AgentState):
    user_input = interrupt("Waiting for closing remarks")
    
    prompt = load_prompt("end.md").invoke({})
    structured_llm = llm.with_structured_output(EndOutput)
    
    messages = [SystemMessage(content=system_prompt_content)] + state["messages"] + [HumanMessage(content=user_input)]
    messages.append(SystemMessage(content=prompt.to_string()))
    
    response = structured_llm.invoke(messages)
    
    return {
        "messages": [HumanMessage(content=user_input), AIMessage(content=response.ai_response)],
        "next_node": response.next_node
    }

# --- Runtime Node Router ---

def route_next_node(state: AgentState) -> str:
    """Explicit conditional routing driven by LLM structured outputs."""
    return state["next_node"]

# --- Build Graph ---

builder = StateGraph(AgentState)

builder.add_node("start", start_node)
builder.add_node("provider_intake", provider_intake_node)
builder.add_node("patient_intake", patient_intake_node)
builder.add_node("auth_intake", auth_intake_node)
builder.add_node("lookup", lookup_node)
builder.add_node("end_call", end_call_node)

builder.add_edge(START, "start")
builder.add_conditional_edges("start", route_next_node)
builder.add_conditional_edges("provider_intake", route_next_node)
builder.add_conditional_edges("patient_intake", route_next_node)
builder.add_conditional_edges("auth_intake", route_next_node)
builder.add_conditional_edges("lookup", route_next_node)
builder.add_conditional_edges("end_call", route_next_node, {"END": END})

from langgraph.checkpoint.memory import MemorySaver
memory = MemorySaver()
app = builder.compile(checkpointer=memory)