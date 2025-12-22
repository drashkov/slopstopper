import argparse
import os
import json
import logging
from typing import Optional
import time

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn
from dotenv import load_dotenv
from sqlite_utils import Database
from google import genai
from google.genai import types

from src.schema import VideoAnalysis, get_schema_json
from src.prompts import SYSTEM_INSTRUCTION_V1

# Log config - File only to prevent interference with Rich Live display
logging.basicConfig(
    level=logging.INFO, 
    format="%(asctime)s - %(levelname)s - %(message)s",
    filename="slopstopper.log",
    filemode="a"
)
# Force terminal to prevent "dumb" fallbacks in some envs
console = Console(force_terminal=True)
load_dotenv()

DB_FILE = "data/slopstopper.db"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Model Configuration
MODEL_DEFAULT = "gemini-2.5-flash-lite"
MODEL_PREVIEW = "gemini-3-flash-preview"

# Price per million tokens (Input + Output averaged for simplicity or specific?)
# User specified: 0.10 and 0.30 per million. 
# We'll treat this as a flat rate for now or apply to both input/output.
# Usually pricing differs for input/output but user gave single numbers.
# I will apply it to total tokens.
PRICE_PER_MILLION = {
    MODEL_DEFAULT: 0.10,
    MODEL_PREVIEW: 0.30
}

# CHANGE THIS TO SWITCH MODELS
CURRENT_MODEL = MODEL_PREVIEW

def get_db():
    return Database(DB_FILE)

def construct_prompt(title: str, video_url: str) -> str:
    return f"""
    Title: {title}
    URL: {video_url}
    
    Analyze the video based on the system instructions.
    """

def analyze_video(client, video_id: str, title: str, model_name: str = CURRENT_MODEL):
    """
    Calls Gemini API to analyze the video.
    """
    
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    prompt = construct_prompt(title, video_url)

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION_V1,
                response_mime_type="application/json",
                response_schema=VideoAnalysis
            )
        )
        
        return response
    except Exception as e:
        logging.error(f"Gemini Analysis Failed: {e}")
        return None



# ... (imports remain)

import concurrent.futures
import threading

# ... (imports remain)

def main():
    parser = argparse.ArgumentParser(description="SlopStopper Analysis")
    parser.add_argument("--ids", nargs="+", help="Specific Video IDs to analyze")
    parser.add_argument("--all", action="store_true", help="Analyze all PENDING videos")
    parser.add_argument("--limit", type=int, help="Analyze the first N pending videos")
    parser.add_argument("--workers", type=int, default=5, help="Number of concurrent workers (1-20)")
    args = parser.parse_args()

    # Cap workers at 20
    max_workers = max(1, min(args.workers, 20))

    # ... (Keep existing checks/DB loading)
    if not GEMINI_API_KEY and not os.getenv("MOCK_GEMINI"):
         console.print("[bold red]Error: GEMINI_API_KEY not set.[/bold red]")
         return

    db = get_db()
    
    if args.ids:
        rows = list(db["videos"].rows_where(f"video_id in ({','.join(['?']*len(args.ids))})", args.ids))
    elif args.limit:
        rows = list(db["videos"].rows_where("status = 'PENDING'", limit=args.limit))
    elif args.all:
        rows = list(db["videos"].rows_where("status = 'PENDING'"))
    else:
        console.print("Please specify --ids, --limit, or --all")
        return

    # Sharing Client? Google GenAI Client is thread-safe usually.
    # We will instantiate inside main.
    client = None
    if GEMINI_API_KEY:
        client = genai.Client(api_key=GEMINI_API_KEY)

    # Shared State & Locks
    state = {
        "cost": 0.0,
        "in": 0,
        "out": 0,
        "processed": 0
    }
    lock = threading.Lock()

    # Helper to calculate cost
    def calc_cost(in_tok, out_tok, model):
        price = PRICE_PER_MILLION.get(model, 0.0)
        return ((in_tok + out_tok) / 1_000_000) * price

    # Setup Progress Bar with Rolling Log
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        console=console
    ) as progress:
        
        task_id = progress.add_task(f"[cyan]Initializing ({max_workers} workers)...", total=len(rows))
        
        # Print Header
        progress.console.print(f"[bold white]{'Video ID':<12} | {'Title':<35} | {'Verdict':<15} | {'Tokens':<12} | {'Cost':<10}[/bold white]")
        progress.console.print("[dim]" + "-"*95 + "[/dim]")
        
        def process_single_video(row):
            video_id = row['video_id']
            title = row['title']
            
            # MOCK LOGIC
            if os.getenv("MOCK_GEMINI"):
                time.sleep(0.5) 
                action = "Approve"
                in_tok, out_tok = 100, 50
                cost = calc_cost(in_tok, out_tok, CURRENT_MODEL)
                
                with lock:
                    state["in"] += in_tok
                    state["out"] += out_tok
                    state["cost"] += cost
                    state["processed"] += 1
                    current_cost = state["cost"]
                
                # UI Update (Thread safe via rich)
                # Helper to print row
                vid_s = video_id[:12]
                tit_s = (title[:32] + "...") if len(title) > 35 else title
                tit_s = tit_s.ljust(35)
                # Colorize Verdict
                if "Block" in action or "Error" in action: v_col = "red"
                elif "Monitor" in action: v_col = "yellow"
                else: v_col = "green"
                verdict_s = f"[{v_col}]{action:<15}[/{v_col}]"
                tok_s = f"{in_tok}/{out_tok}"
                cost_s = f"${cost:.6f}"
                progress.console.print(f"{vid_s:<12} | {tit_s} | {verdict_s} | {tok_s:<12} | {cost_s:<10}")

                progress.update(task_id, advance=1, description=f"[cyan]Analyzing ({max_workers} threads)... Cost: ${current_cost:.4f}")
                return

            if not client:
                 progress.update(task_id, advance=1)
                 return

            # REAL API CALL
            # Note: client usage might need catching if not thread safe, but standard clients usually are.
            try:
                response = analyze_video(client, video_id, title)
            except Exception as e:
                # Fallback error catch
                response = None
                logging.error(f"Generate Content Error: {e}")

            if response and response.text:
                try:
                    analysis_data = VideoAnalysis.model_validate_json(response.text)
                    
                    in_tok = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
                    out_tok = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
                    cost = calc_cost(in_tok, out_tok, CURRENT_MODEL)
                    
                    with lock:
                        state["in"] += in_tok
                        state["out"] += out_tok
                        state["cost"] += cost
                        current_cost = state["cost"]

                    # Update DB (Thread-Local Connection)
                    thread_db = Database(DB_FILE)
                    thread_db["videos"].update(video_id, {
                        "status": "ANALYZED",
                        "analysis_json": response.text,
                        "safety_score": analysis_data.risk_assessment.safety_score,
                        "primary_genre": analysis_data.content_taxonomy.primary_genre.value,
                        "is_slop": analysis_data.cognitive_nutrition.is_slop,
                        "is_brainrot": analysis_data.cognitive_nutrition.is_brainrot,
                        "is_short": analysis_data.video_metadata.format == "Short_Vertical",
                        "model_used": CURRENT_MODEL,
                        "input_tokens": in_tok,
                        "output_tokens": out_tok,
                        "estimated_cost": cost,
                    })
                    
                    # Print Row
                    action = analysis_data.verdict.action.value
                    vid_s = video_id[:12]
                    tit_s = (title[:32] + "...") if len(title) > 35 else title
                    tit_s = tit_s.ljust(35)
                    if "Block" in action or "Error" in action: v_col = "red"
                    elif "Monitor" in action: v_col = "yellow"
                    else: v_col = "green"
                    verdict_s = f"[{v_col}]{action:<15}[/{v_col}]"
                    progress.console.print(f"{vid_s:<12} | {tit_s} | {verdict_s} | {in_tok}/{out_tok:<12} | ${cost:.6f}")
                    
                except Exception as e:
                    logging.error(f"Failed to process response for {video_id}: {e}")
                    thread_db = Database(DB_FILE)
                    thread_db["videos"].update(video_id, {"status": "ERROR", "error_log": str(e)})
                    progress.console.print(f"{video_id[:12]} | {title[:20]:<35} | [red]Error[/red]           | 0/0          | $0.000000")
            else:
                 thread_db = Database(DB_FILE)
                 thread_db["videos"].update(video_id, {"status": "ERROR", "error_log": "No response from Gemini"})
                 progress.console.print(f"{video_id[:12]} | {title[:20]:<35} | [red]No Resp[/red]         | 0/0          | $0.000000")

            with lock:
                state["processed"] += 1
                current_cost = state["cost"]
                
            progress.update(task_id, advance=1, description=f"[cyan]Analyzing ({max_workers} threads)... Cost: ${current_cost:.4f}")

        # Execute Concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            futures = [executor.submit(process_single_video, row) for row in rows]
            concurrent.futures.wait(futures)

    console.print(f"[bold green]Analysis Complete. Total Estimated Cost: ${state['cost']:.6f}[/bold green]")

if __name__ == "__main__":
    main()
