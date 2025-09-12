from vertexai import agent_engines
from dotenv import load_dotenv
import pprint
import json 
import os

load_dotenv()

ORCHESTRATE_AGENT_ID = os.environ.get('ORCHESTRATE_AGENT_ID')

def call_orchestrator_agent(user_name: str, user_prompt: str):
    """
    Calls the orchestrator agent with a user's request and yields the agent's thought process.
    """
    agent_engine = agent_engines.get(ORCHESTRATE_AGENT_ID)
    if not agent_engine:
        yield {"type": "error", "data": {"message": "ORCHESTRATE_AGENT_ID not set or agent engine failed to initialize."}}
        return

    user_id = str(user_name) # Use username as the session ID

    yield {"type": "thought", "data": f"--- Orchestrator Agent Call Initiated ---"}
    yield {"type": "thought", "data": f"Session ID for this run: {user_id}"}
    yield {"type": "thought", "data": f"User: {user_name}"}
    yield {"type": "thought", "data": f"Prompt: {user_prompt}"}

    # The prompt for the orchestrator should be a high-level task.
    # The orchestrator's root instruction will guide it to break this down.
    prompt_message = f"""
    The current logged in user is {user_name}.
    Your task is to design a fun collage for {user_name} based on his request.

    Here are the details for the collage to be made:
    - Instruction for collage: {user_prompt}
    - Once the collage is created, post it to the Google Photos app

    Your process should be:
    1. Analyze the input request. If you have access to a tool to get the names of relevant people, please use it.
    2. Analyze the determined names. If you have access to a tool to get their photographs, please use it.
    3. Based on the fetched photos, if you have access to a tool to create a collage out of them, please use it.
    4. Based on the created collage, if you have access to a tool that posts the collage to the Google photos app, please use it.
    5. If you don't find any photos, inform that you will be not able to create a collage.
    """

    print(f"--- Sending Prompt to Orchestrator Agent ---")
    print(prompt_message)
    yield {"type": "thought", "data": f"Sending high-level task to orchestrator agent."}

    accumulated_response = ""
    yield {"type": "thought", "data": f"--- Agent Response Stream Starting ---"}

    try:
        for event_idx, event in enumerate(
           agent_engine.stream_query(
                user_id=user_id,
                message=prompt_message,
            )
        ):
            print(f"\n--- Event {event_idx} Received ---") # Console
            pprint.pprint(event) # Console
            try:
                content = event.get('content', {})
                parts = content.get('parts', [])

                if not parts:
                    continue

                for part_idx, part in enumerate(parts):
                    if isinstance(part, dict):
                        text = part.get('text')
                        if text:
                            yield {"type": "thought", "data": f"Agent: \"{text}\""}
                            accumulated_response += text
                        else:
                            tool_code = part.get('tool_code')
                            tool_code_output = part.get('tool_code_output')
                            if tool_code:
                                tool_name = tool_code.get('name', 'Unnamed tool')
                                # The orchestrator's only tool is 'send_message'
                                if tool_name == 'send_message':
                                    args = tool_code.get('args', {})
                                    remote_agent = args.get('agent_name')
                                    task = args.get('task')
                                    yield {"type": "thought", "data": f"Orchestrator is delegating a task to the '{remote_agent}' agent: '{task}'"}
                                else:
                                    yield {"type": "thought", "data": f"Agent is considering tool: {tool_name}."}
                            if tool_code_output:
                                yield {"type": "thought", "data": f"Orchestrator received output from a tool call."}
            except Exception as e_inner:
                yield {"type": "thought", "data": f"Error processing agent event part {event_idx}: {str(e_inner)}"}

    except Exception as e_outer:
        yield {"type": "thought", "data": f"Critical error during agent stream query: {str(e_outer)}"}
        yield {"type": "error", "data": {"message": f"Error during agent interaction: {str(e_outer)}", "raw_output": accumulated_response}}
        return # Stop generation

    yield {"type": "thought", "data": f"--- End of Agent Response Stream ---"}

    if accumulated_response:
        yield {"type": "final_response", "data": accumulated_response}
    else:
        yield {"type": "thought", "data": "Agent did not provide any final text content in its response."}
        yield {"type": "final_response", "data": "Processing complete."}