import json
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field

# --- DIMENSION 1: VISUAL GROUNDING ---
class VisualGrounding(BaseModel):
    detected_entities: List[str] = Field(description="List 3-5 main visual elements (e.g., 'Roblox UI', 'Minecraft Steve', 'Text Overlay', 'Toy Car').")
    setting: str = Field(description="e.g., 'Bedroom', 'Game World', 'Studio'.")
    text_on_screen: Optional[str] = Field(None, description="Quote any prominent text overlays.")

# --- DIMENSION 2: TAXONOMY (The Diet) ---
class VideoFormat(str, Enum):
    STANDARD_LANDSCAPE = "Standard_Landscape"
    SHORT_VERTICAL = "Short_Vertical"
    LIVESTREAM_VOD = "Livestream_VOD"
    UNKNOWN = "Unknown"

class DurationPerceived(str, Enum):
    MICRO = "Micro (<1 min)"
    SHORT = "Short (1-5 min)"
    MEDIUM = "Medium (5-20 min)"
    LONG = "Long (20+ min)"

class VideoMetadata(BaseModel):
    format: VideoFormat
    duration_perceived: DurationPerceived

class PrimaryGenre(str, Enum):
    GAMING_GAMEPLAY = "Gaming_Gameplay"
    GAMING_CULTURE = "Gaming_Culture"
    ANIMATION_STORYTIME = "Animation_Storytime"
    ANIMATION_CONTENTFARM = "Animation_ContentFarm"
    TOYS_UNBOXING = "Toys_Unboxing"
    PRANKS_CHALLENGES = "Pranks_Challenges"
    EDUCATION_STEM = "Education_STEM"
    EDUCATION_HUMANITIES = "Education_Humanities"
    MASCOT_HORROR = "Mascot_Horror"
    INTERNET_CULTURE = "Internet_Culture"
    VLOG_LIFESTYLE = "Vlog_Lifestyle"
    MUSIC_DANCE = "Music_Dance"
    PSEUDOSCIENCE_CONSPIRACY = "Pseudoscience_Conspiracy"
    OTHER = "Other"

class TargetDemographic(str, Enum):
    TODDLER = "Toddler (0-4)"
    CHILD = "Child (5-9)"
    PRE_TEEN = "Pre-Teen (10-12)"
    TEEN = "Teen (13+)"
    ADULT = "Adult"

class ContentTaxonomy(BaseModel):
    primary_genre: PrimaryGenre
    specific_topic: str = Field(description="e.g., 'Pet Simulator 99', 'Skibidi Toilet', 'Black Holes'.")
    target_demographic: TargetDemographic

# --- DIMENSION 3: NARRATIVE QUALITY (The Craft) ---
class StructuralIntegrity(str, Enum):
    COHERENT_NARRATIVE = "Coherent_Narrative"
    LOOSE_VLOG_STYLE = "Loose_Vlog_Style"
    COMPILATION_CLIPS = "Compilation_Clips"
    INCOHERENT_CHAOS = "Incoherent_Chaos"

class CreativeIntent(str, Enum):
    ARTISTIC_CREATIVE = "Artistic/Creative"
    INFORMATIONAL = "Informational"
    PARASOCIAL_VLOG = "Parasocial/Vlog"
    ALGORITHMIC_SLOP = "Algorithmic/Slop"

class WeirdnessVerdict(str, Enum):
    NORMAL = "Normal"
    CREATIVE_SURREALISM = "Creative_Surrealism"
    DISTURBING_UNCANNY = "Disturbing_Uncanny"
    LAZY_RANDOMNESS = "Lazy_Randomness"

class NarrativeQuality(BaseModel):
    structural_integrity: StructuralIntegrity = Field(description="'Coherent' has a clear start/end. 'Incoherent' is random noise.")
    creative_intent: CreativeIntent = Field(description="Does it feel like a human vision or an algorithm hack?")
    weirdness_verdict: WeirdnessVerdict = Field(description="Distinguishes high-effort weirdness (Surrealism) from low-effort noise (Lazy).")

# --- DIMENSION 4: COGNITIVE NUTRITION (The Impact) ---
class IntellectualDensity(str, Enum):
    VOID = "Void (Mindless)"
    LOW = "Low (Trivia)"
    MEDIUM = "Medium (Story/Hobby)"
    HIGH = "High (Educational)"

class EmotionalVolatility(str, Enum):
    CALM = "Calm"
    UPBEAT = "Upbeat"
    HIGH_STRESS = "High_Stress"
    AGGRESSIVE_SCREAMING = "Aggressive_Screaming"

class CognitiveNutrition(BaseModel):
    intellectual_density: IntellectualDensity
    emotional_volatility: EmotionalVolatility = Field(description="Does the creator scream/rage to spike cortisol?")
    is_brainrot: bool = Field(description="Rapid-fire editing, sensory overload, retention hacking.")
    is_slop: bool = Field(description="Low-effort, soul-less production.")

# --- DIMENSION 5: RISK ASSESSMENT (The Safety) ---
class RiskFlags(BaseModel):
    ideological_radicalization: bool = Field(description="Alt-right, misogyny, intolerance.")
    pseudoscience_misinfo: bool = Field(description="Falsehoods, anti-science.")
    body_image_harm: bool = Field(description="Looksmaxxing, steroids.")
    dangerous_behavior: bool = Field(description="Stunts, bullying.")
    commercial_exploitation: bool = Field(description="Aggressive merch pushing.")
    lootbox_gambling: bool = Field(description="Gacha mechanics, digital scarcity pressure.")
    sexual_themes: bool
    mascot_horror: bool = Field(description="Huggy Wuggy, etc.")

class RiskAssessment(BaseModel):
    safety_score: int = Field(description="0-100 score.")
    flags: RiskFlags

# --- SUMMARY & VERDICT ---
class ActionVerdict(str, Enum):
    APPROVE = "Approve"
    MONITOR = "Monitor"
    BLOCK_VIDEO = "Block_Video"
    BLOCK_CHANNEL = "Block_Channel"

class Verdict(BaseModel):
    action: ActionVerdict
    reason: str

class VideoAnalysis(BaseModel):
    visual_grounding: VisualGrounding = Field(description="Objective listing of what is physically seen. Do not interpret yet.")
    video_metadata: VideoMetadata
    content_taxonomy: ContentTaxonomy
    narrative_quality: NarrativeQuality
    cognitive_nutrition: CognitiveNutrition
    risk_assessment: RiskAssessment
    summary: str = Field(description="Cynical summary of intent.")
    verdict: Verdict

def get_schema_json():
    return json.dumps(VideoAnalysis.model_json_schema(), indent=2)
