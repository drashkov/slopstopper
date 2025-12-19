import json
import logging
from pathlib import Path
from datetime import datetime
from sqlite_utils import Database

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

HISTORY_FILE = Path("data/watch-history.json") # Updated to point to the file in root
DB_FILE = Path("data/slopstopper.db")

def init_db():
    db = Database(DB_FILE)
    videos = db["videos"]
    if not videos.exists():
        videos.create({
            "video_id": str,
            "title": str,
            "video_url": str,
            "channel_name": str,
            "channel_url": str,
            "watch_timestamp": datetime,
            "status": str,
            "error_log": str,
            "model_used": str,
            "prompt_version": str,
            "input_tokens": int,
            "output_tokens": int,
            "estimated_cost": float,
            "safety_score": int,
            "primary_genre": str,
            "is_slop": bool,
            "is_brainrot": bool,
            "is_short": bool,
            "analysis_json": str
        }, pk="video_id", if_not_exists=True)
        logging.info("Database initialized.")
    return db

def parse_iso_time(time_str):
    try:
        return datetime.fromisoformat(time_str.replace("Z", "+00:00"))
    except ValueError:
        return None

def extract_video_id(url):
    if "v=" in url:
        return url.split("v=")[1]
    return None

def process_history():
    if not HISTORY_FILE.exists():
        logging.error(f"File not found: {HISTORY_FILE}")
        return

    with open(HISTORY_FILE, "r") as f:
        data = json.load(f)

    db = init_db()
    table = db["videos"]
    
    # Pre-load existing IDs for accurate duplicate counting
    existing_ids = set()
    try:
        existing_ids = {r["video_id"] for r in table.rows}
    except Exception:
        pass # Table might be empty

    total_json_entries = len(data)
    skipped_metadata = 0
    duplicates_count = 0
    added_count = 0

    for entry in data:
        # Basic Validation
        if entry.get("header") != "YouTube":
            skipped_metadata += 1
            continue
            
        title = entry.get("title", "").replace("Watched ", "")
        video_url = entry.get("titleUrl", "")
        video_id = extract_video_id(video_url)
        
        if not video_id:
            skipped_metadata += 1
            continue

        # Check Duplicates
        if video_id in existing_ids:
            duplicates_count += 1
            continue # Skip insertion

        # Extract Channel Info
        subtitles = entry.get("subtitles", [])
        channel_name = subtitles[0].get("name") if subtitles else "Unknown"
        channel_url = subtitles[0].get("url") if subtitles else ""
        
        timestamp = parse_iso_time(entry.get("time", ""))

        # Prepare record
        record = {
            "video_id": video_id,
            "title": title,
            "video_url": video_url,
            "channel_name": channel_name,
            "channel_url": channel_url,
            "watch_timestamp": timestamp,
            "status": "PENDING"
        }
        
        try:
            table.insert(record, pk="video_id")
            added_count += 1
            existing_ids.add(video_id)
        except Exception as e:
            logging.error(f"Error inserting {video_id}: {e}")
        
    logging.info(f"--- Ingestion Report ---")
    logging.info(f"Total Entries in JSON: {total_json_entries}")
    logging.info(f"Skipped (Invalid/No ID): {skipped_metadata}")
    logging.info(f"Duplicates (Already in DB or repeated in JSON): {duplicates_count}")
    logging.info(f"New Videos Added: {added_count}")

if __name__ == "__main__":
    process_history()
