import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langchain_core.tools import tool

@tool
def dummy():
    """Dummy tool"""
    return "ok"

llm = ChatGoogleGenerativeAI(model="gemini-3-flash-preview")
print("Initializing agent...")
try:
    agent = create_react_agent(llm, tools=[dummy], state_modifier="You are a helper.")
    print("Agent initialized successfully!")
except Exception as e:
    print(f"Error during initialization: {e}")
    import traceback
    traceback.print_exc()
