import argparse
import os
import logging
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from dotenv import load_dotenv
from google import genai
from google.genai import types

from src.analyze import get_db, construct_prompt, analyze_video, MODEL_DEFAULT, MODEL_PREVIEW
from src.schema import VideoAnalysis
from src.prompts import SYSTEM_INSTRUCTION_V1

# Log config
logging.basicConfig(level=logging.ERROR) # Keep it quiet
console = Console()
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_JUDGE = "gemini-1.5-pro" # Fallback to a known strong model if 3-pro-preview fails, but trying requested first
# Using the requested name:
MODEL_JUDGE_REQUESTED = "gemini-3-pro-preview" 

def main():
    parser = argparse.ArgumentParser(description="SlopStopper Model Comparison")
    parser.add_argument("video_id", help="Video ID to analyze")
    args = parser.parse_args()

    if not GEMINI_API_KEY and not os.getenv("MOCK_GEMINI"):
         console.print("[bold red]Error: GEMINI_API_KEY not set.[/bold red]")
         return

    db = get_db()
    # Find title
    rows = list(db["videos"].rows_where("video_id = ?", [args.video_id]))
    if not rows:
        console.print(f"[red]Video {args.video_id} not found in DB.[/red]")
        return
    
    title = rows[0]["title"]
    video_url = f"https://www.youtube.com/watch?v={args.video_id}"
    
    console.print(f"[bold cyan]Comparing Models for:[/bold cyan] {title} ({args.video_id})")
    
    # Construct Prompt
    prompt_text = construct_prompt(title, video_url)
    console.print(Panel(prompt_text, title="Prompt Used", border_style="blue"))
    
    client = None
    if GEMINI_API_KEY:
        client = genai.Client(api_key=GEMINI_API_KEY)
    elif os.getenv("MOCK_GEMINI"):
        console.print("[yellow]Running in MOCK mode[/yellow]")
        # Mock responses
        resp_a_text = '{"summary": "Mock A", "verdict": {"action": "Approve"}}'
        resp_b_text = '{"summary": "Mock B", "verdict": {"action": "Monitor"}}'
    
    inputs = {
        "A": {"model": MODEL_DEFAULT, "response": None},
        "B": {"model": MODEL_PREVIEW, "response": None}
    }

    if client:
        with console.status("Running Models..."):
            # Run Model A
            resp_a = analyze_video(client, args.video_id, title, model_name=inputs["A"]["model"])
            inputs["A"]["response"] = resp_a.text if resp_a else "Error"

            # Run Model B
            resp_b = analyze_video(client, args.video_id, title, model_name=inputs["B"]["model"])
            inputs["B"]["response"] = resp_b.text if resp_b else "Error"
    elif os.getenv("MOCK_GEMINI"):
        inputs["A"]["response"] = resp_a_text
        inputs["B"]["response"] = resp_b_text
        
    # Display Responses
    for key, data in inputs.items():
        console.print(Panel(data["response"], title=f"Response {key} ({data['model']})", border_style="green" if key == "A" else "yellow"))

    # Judge
    judge_prompt = f"""
    You are an expert evaluator of AI safety systems.
    
    ORIGINAL SYSTEM INSTRUCTION:
    {SYSTEM_INSTRUCTION_V1}
    
    USER PROMPT:
    {prompt_text}
    
    RESPONSE A ({inputs['A']['model']}):
    {inputs["A"]["response"]}
    
    RESPONSE B ({inputs['B']['model']}):
    {inputs["B"]["response"]}
    
    TASK:
    Compare the two responses. Which one better adheres to the "cynical parent" persona and provides a more accurate, useful analysis based on the JSON schema?
    Provide a brief reasoning and pick a winner (A or B).
    """
    
    console.print(Panel("Asking the Judge...", style="bold magenta"))
    
    if client:
        try:
            # Try requested model, distinct catch for fallback? 
            # Or just use the requested one.
            response = client.models.generate_content(
                model=MODEL_JUDGE_REQUESTED,
                contents=judge_prompt
            )
            console.print(Markdown(response.text))
        except Exception as e:
            console.print(f"[red]Judge ({MODEL_JUDGE_REQUESTED}) failed: {e}[/red]")
            console.print("[yellow]Falling back to gemini-1.5-pro...[/yellow]")
            try:
                response = client.models.generate_content(
                    model="gemini-1.5-pro",
                    contents=judge_prompt
                )
                console.print(Markdown(response.text))
            except Exception as e2:
                console.print(f"[red]Fallback Judge failed: {e2}[/red]")
    elif os.getenv("MOCK_GEMINI"):
        console.print(Markdown("### Judge Verdict (Mock)\n**Winner: A**\n\nReasoning: A was more cynical."))

if __name__ == "__main__":
    main()
