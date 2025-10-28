import os
import random
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId

from database import db, create_document, get_documents
from schemas import Story, Chapter

app = FastAPI(title="AI Storybook Generator API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Utility -----------------
class GenerateRequest(BaseModel):
    title: str
    theme: Optional[str] = None
    audience: str = Field("children")
    style: Optional[str] = None
    tone: Optional[str] = None
    moral: Optional[str] = None
    setting: Optional[str] = None
    language: str = Field("en")
    characters: List[str] = Field(default_factory=list)
    chapters: int = Field(5, ge=1, le=15)
    save: bool = Field(True)

class GenerateResponse(BaseModel):
    system_prompt: str
    story: Story
    id: Optional[str] = None

# ----------------- System Prompt -----------------
SYSTEM_PROMPT = (
    "You are FLAMES.BLUE — a next-generation, god-tier Storybook Architect. "
    "Your purpose is to craft captivating, age-appropriate, culturally sensitive, and imaginative storybooks. "
    "Principles: (1) Coherent multi-chapter arcs with setup, escalation, climax, and resolution. "
    "(2) Distinct character voices and consistent traits. (3) Vivid sensory imagery and scene framing. "
    "(4) Positive values; no explicit content. (5) Rich but accessible vocabulary tuned to audience. "
    "(6) Inclusive, kind, and empowering narratives. (7) Strong pacing: each chapter advances plot. "
    "(8) Subtle callbacks and foreshadowing. (9) End with a concise moral or reflection when requested. "
    "Output strictly in requested language and length. Use clean prose; avoid numbered lists unless asked."
)

@app.get("/api/prompt/system")
def get_system_prompt():
    return {"system_prompt": SYSTEM_PROMPT}

# ----------------- Lightweight Local Generator -----------------
# This is a rule-based generator designed to work offline and free of API keys
# while producing engaging multi-chapter stories.

def _make_chapter_title(title: str, idx: int, style: Optional[str], tone: Optional[str]) -> str:
    seeds = [
        "A New Beginning", "Whispers in the Wind", "The Hidden Path", "A Promise at Dawn",
        "Shadows and Starlight", "Secrets of the {setting}", "Turning the Tide", "The Heart Remembers",
        "Trials of Courage", "Home Again"
    ]
    base = seeds[(idx - 1) % len(seeds)]
    if style:
        base = f"{base} — {style.title()}"
    if tone:
        base = f"{base} ({tone.title()})"
    if title:
        return f"Chapter {idx}: {base}"
    return f"Chapter {idx}: {base}"


def _paragraph(theme: Optional[str], setting: Optional[str], audience: str, characters: List[str]) -> str:
    who = ", ".join(characters[:3]) if characters else "a small band of friends"
    place = setting or "a place where the sky feels close and the air hums with possibility"
    voice = {
        "children": "gentle and curious",
        "teens": "brisk and adventurous",
        "adults": "lyrical and reflective",
    }.get(audience.lower(), "gentle and curious")
    adorn = random.choice([
        "sun-dappled paths", "quiet lanterns", "soft thunder beyond the hills",
        "maps scribbled in the margins", "a pocket full of brave ideas"
    ])
    return (
        f"With a {voice} voice, the tale leans into {theme or 'wonder'}, as {who} step through {place}. "
        f"They carry {adorn}, and with each breath they learn that courage grows when it is shared."
    )


def _chapter_text(idx: int, total: int, theme: Optional[str], setting: Optional[str], audience: str, characters: List[str]) -> str:
    arc = "setup" if idx == 1 else ("climax" if idx == total else ("escalation" if idx < total else "resolution"))
    intro = _paragraph(theme, setting, audience, characters)
    beat = {
        "setup": "They meet a gentle challenge that hints at something larger.",
        "escalation": "The path grows twisty; trust and patience are tested in warm, human ways.",
        "climax": "At last, the heart of the problem opens—difficult, yet navigable with kindness.",
        "resolution": "With lessons gathered, the world feels wider, and home feels new."
    }[arc if idx < total else "resolution"]
    dialogue = " "
    if characters:
        speaker = random.choice(characters)
        friend = random.choice([c for c in characters if c != speaker] or characters)
        dialogue = f"\n\n\"We can do this together,\" {speaker} says. \"We always could,\" {friend} replies."
    return f"{intro} {beat}{dialogue}"


def generate_story(req: GenerateRequest) -> Story:
    chapters: List[Chapter] = []
    for i in range(1, req.chapters + 1):
        chapters.append(
            Chapter(
                index=i,
                title=_make_chapter_title(req.title, i, req.style, req.tone),
                text=_chapter_text(i, req.chapters, req.theme, req.setting, req.audience, req.characters),
            )
        )
    cover_prompt = (
        f"Illustrated cover in a cozy, luminous style. Title: '{req.title}'. "
        f"Theme: {req.theme or 'wonder'}. Setting: {req.setting or 'imaginative landscape'}. "
        f"Characters: {', '.join(req.characters) or 'a group of friends'}."
    )
    story = Story(
        title=req.title,
        theme=req.theme,
        audience=req.audience,
        style=req.style,
        tone=req.tone,
        moral=req.moral,
        setting=req.setting,
        language=req.language,
        characters=req.characters,
        chapters=chapters,
        cover_prompt=cover_prompt,
        generator_version="1.0-local",
    )
    return story

# ----------------- Routes -----------------
@app.post("/api/stories/generate", response_model=GenerateResponse)
def api_generate_story(payload: GenerateRequest):
    story = generate_story(payload)
    inserted_id: Optional[str] = None
    if payload.save:
        inserted_id = create_document("story", story)
    return GenerateResponse(system_prompt=SYSTEM_PROMPT, story=story, id=inserted_id)


@app.get("/api/stories")
def list_stories(limit: int = 20):
    docs = get_documents("story", {}, limit)
    # Convert ObjectId to string
    for d in docs:
        if isinstance(d.get("_id"), ObjectId):
            d["_id"] = str(d["_id"])
    return {"items": docs}


@app.get("/")
def root():
    return {"message": "AI Storybook Generator API is running"}


@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    import os as _os
    response["database_url"] = "✅ Set" if _os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if _os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
