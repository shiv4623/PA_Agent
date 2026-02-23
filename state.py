from typing import Annotated, Optional, Literal
from typing_extensions import TypedDict
from pydantic import BaseModel, Field
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage
import warnings
warnings.filterwarnings("ignore")

class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    provider_name: Optional[str]
    provider_callback: Optional[str]
    patient_name: Optional[str]
    patient_dob: Optional[str]
    member_id: Optional[str]
    auth_id: Optional[str]
    procedure: Optional[str]
    next_node: str

# --- Pydantic Structured Outputs for LLMs ---

class ProviderOutput(BaseModel):
    provider_name: Optional[str] = Field(description="Extracted provider name")
    provider_callback: Optional[str] = Field(description="Extracted 10-digit callback number")
    ai_response: str = Field(description="The exact text the agent will say next")
    next_node: Literal["provider_intake", "patient_intake"]

class PatientOutput(BaseModel):
    patient_name: Optional[str] = Field(description="Extracted patient name")
    patient_dob: Optional[str] = Field(description="Extracted patient DOB")
    member_id: Optional[str] = Field(description="Extracted member ID")
    ai_response: str = Field(description="The exact text the agent will say next")
    next_node: Literal["patient_intake", "auth_intake"]

class AuthOutput(BaseModel):
    auth_id: Optional[str] = Field(description="Extracted authorization ID")
    procedure: Optional[str] = Field(description="Extracted procedure name")
    ai_response: str = Field(description="The exact text the agent will say next")
    next_node: Literal["auth_intake", "lookup"]

class LookupOutput(BaseModel):
    ai_response: str = Field(description="The exact text the agent will say next")
    next_node: Literal["end_call"]

class EndOutput(BaseModel):
    ai_response: str = Field(description="The final goodbye message")
    next_node: Literal["END"]