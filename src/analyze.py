import argparse
import os
import json
import logging
from typing import Optional
import time

from rich.console import Console
from rich.progress import track
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

from rich.table import Table
from rich.live import Live
from rich.text import Text
from rich.console import Group

# ... (imports remain)

def main():
    parser = argparse.ArgumentParser(description="SlopStopper Analysis")
    parser.add_argument("--ids", nargs="+", help="Specific Video IDs to analyze")
    parser.add_argument("--all", action="store_true", help="Analyze all PENDING videos")
    parser.add_argument("--limit", type=int, help="Analyze the first N pending videos")
    args = parser.parse_args()

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

    # Helper to calculate cost
    def calc_cost(in_tok, out_tok, model):
        price = PRICE_PER_MILLION.get(model, 0.0)
        return ((in_tok + out_tok) / 1_000_000) * price

    client = None
    if GEMINI_API_KEY:
        client = genai.Client(api_key=GEMINI_API_KEY)
    
    total_cost = 0.0
    total_in = 0
    total_out = 0
    videos_processed = 0
    start_time = time.time()

    # Initialize Table with width constraint and footers
    table = Table(title="Analysis Results", width=80, border_style="cyan", show_footer=True)
    table.add_column("Video ID", style="cyan", no_wrap=True)
    table.add_column("Title", style="white", ratio=2)
    table.add_column("Verdict", style="magenta")
    table.add_column("Tokens (In/Out)", justify="right", style="green", footer="0/0")
    table.add_column("Est. Cost", justify="right", style="yellow", footer="$0.000000")

    # Simple stats text instead of spinner
    stats_text = Text()

    with Live(Group(table, stats_text), console=console, auto_refresh=False) as live:
        for row in rows:
            video_id = row['video_id']
            title = row['title']
            
            # Analysis
            if os.getenv("MOCK_GEMINI"):
                # Mock logic
                time.sleep(0.5) # Simulate latency
                action = "Approve"
                in_tok, out_tok = 100, 50
                cost = calc_cost(in_tok, out_tok, CURRENT_MODEL)
                
                total_in += in_tok
                total_out += out_tok
                total_cost += cost
                
                table.add_row(
                    video_id, 
                    title[:20]+"..." if len(title)>20 else title, 
                    action, 
                    f"{in_tok}/{out_tok}", 
                    f"${cost:.6f}"
                )
                
                # Update footers
                table.columns[3].footer = f"{total_in}/{total_out}"
                table.columns[4].footer = f"${total_cost:.6f}"
                
                videos_processed += 1
                elapsed = time.time() - start_time
                per_video = elapsed / videos_processed if videos_processed else 0
                remaining = len(rows) - videos_processed
                eta = remaining * per_video
                stats_text.plain = f"⏱ Elapsed: {elapsed:.1f}s | ✓ Processed: {videos_processed}/{len(rows)} | ⏳ Per video: {per_video:.1f}s | 🏁 ETA: {eta:.0f}s"
                live.refresh()
                continue

            if not client:
                 continue

            response = analyze_video(client, video_id, title)
            
            if response and response.text:
                try:
                    analysis_data = VideoAnalysis.model_validate_json(response.text)
                    
                    in_tok = response.usage_metadata.prompt_token_count if response.usage_metadata else 0
                    out_tok = response.usage_metadata.candidates_token_count if response.usage_metadata else 0
                    cost = calc_cost(in_tok, out_tok, CURRENT_MODEL)
                    
                    total_in += in_tok
                    total_out += out_tok
                    total_cost += cost

                    # Update DB
                    db["videos"].update(video_id, {
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
                    
                    table.add_row(
                        video_id, 
                        title[:20]+"..." if len(title)>20 else title, 
                        analysis_data.verdict.action.value, 
                        f"{in_tok}/{out_tok}", 
                        f"${cost:.6f}"
                    )
                    
                    # Update footers
                    table.columns[3].footer = f"{total_in}/{total_out}"
                    table.columns[4].footer = f"${total_cost:.6f}"
                    
                except Exception as e:
                    logging.error(f"Failed to process response for {video_id}: {e}")
                    db["videos"].update(video_id, {"status": "ERROR", "error_log": str(e)})
                    table.add_row(video_id, title[:15], f"ERR: {str(e)[:10]}", "-", "-")
            else:
                 db["videos"].update(video_id, {"status": "ERROR", "error_log": "No response from Gemini"})
                 table.add_row(video_id, title[:15], "ERR: No Resp", "-", "-")

            videos_processed += 1
            elapsed = time.time() - start_time
            per_video = elapsed / videos_processed if videos_processed else 0
            remaining = len(rows) - videos_processed
            eta = remaining * per_video
            stats_text.plain = f"⏱ Elapsed: {elapsed:.1f}s | ✓ Processed: {videos_processed}/{len(rows)} | ⏳ Per video: {per_video:.1f}s | 🏁 ETA: {eta:.0f}s"
            live.refresh()

    console.print(f"[bold green]Analysis Complete. Total Estimated Cost: ${total_cost:.6f}[/bold green]")

if __name__ == "__main__":
    main()
