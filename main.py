import os
import random
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from bson import ObjectId
from urllib.parse import quote

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
    include_images: bool = Field(True, description="Whether to generate inline SVG illustrations")

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

PALETTES = [
    ("#f0abfc", "#60a5fa", "#c4b5fd"),
    ("#fda4af", "#a78bfa", "#7dd3fc"),
    ("#bef264", "#34d399", "#93c5fd"),
    ("#fef08a", "#f472b6", "#93c5fd"),
]


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


def _initials(chars: List[str]) -> str:
    if not chars:
        return "★"
    initials = [c.strip()[0].upper() for c in chars if c.strip()]
    return "".join(initials[:3]) or "★"


def _svg_data_url(svg: str) -> str:
    return f"data:image/svg+xml;charset=utf-8,{quote(svg)}"


def _chapter_image_svg(title: str, idx: int, total: int, prompt: str, chars: List[str]) -> str:
    p = random.choice(PALETTES)
    initials = _initials(chars)
    svg = f"""
<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='675' viewBox='0 0 1200 675'>
  <defs>
    <linearGradient id='g{idx}' x1='0' y1='0' x2='1' y2='1'>
      <stop offset='0%' stop-color='{p[0]}'/>
      <stop offset='50%' stop-color='{p[1]}'/>
      <stop offset='100%' stop-color='{p[2]}'/>
    </linearGradient>
  </defs>
  <rect width='1200' height='675' fill='url(#g{idx})' />
  <g opacity='0.2'>
    <circle cx='200' cy='200' r='140' fill='white'/>
    <circle cx='1000' cy='140' r='110' fill='white'/>
    <circle cx='900' cy='520' r='160' fill='white'/>
  </g>
  <text x='50%' y='48%' dominant-baseline='middle' text-anchor='middle' font-family='Inter, system-ui, sans-serif' font-weight='800' font-size='140' fill='rgba(0,0,0,0.25)'>{initials}</text>
  <text x='50%' y='75%' dominant-baseline='middle' text-anchor='middle' font-family='Inter, system-ui, sans-serif' font-weight='700' font-size='36' fill='rgba(0,0,0,0.85)'>Chapter {idx} / {total}</text>
  <text x='50%' y='84%' dominant-baseline='middle' text-anchor='middle' font-family='Inter, system-ui, sans-serif' font-weight='600' font-size='28' fill='rgba(0,0,0,0.85)'>""".strip()
    # Split long title lines
    title_line = title.replace("Chapter ", "")
    svg += title_line
    svg += "</text>\n"
    svg += f"<title>{prompt}</title>\n"
    svg += "</svg>"
    return _svg_data_url(svg)


def _cover_image_svg(title: str, prompt: str, chars: List[str]) -> str:
    p = random.choice(PALETTES)
    initials = _initials(chars)
    svg = f"""
<svg xmlns='http://www.w3.org/2000/svg' width='1200' height='1600' viewBox='0 0 1200 1600'>
  <defs>
    <linearGradient id='gcover' x1='0' y1='0' x2='1' y2='1'>
      <stop offset='0%' stop-color='{p[0]}'/>
      <stop offset='60%' stop-color='{p[1]}'/>
      <stop offset='100%' stop-color='{p[2]}'/>
    </linearGradient>
  </defs>
  <rect width='1200' height='1600' fill='url(#gcover)' />
  <g opacity='0.15'>
    <circle cx='300' cy='400' r='220' fill='white'/>
    <circle cx='1000' cy='300' r='160' fill='white'/>
    <circle cx='800' cy='1200' r='260' fill='white'/>
  </g>
  <text x='50%' y='45%' dominant-baseline='middle' text-anchor='middle' font-family='Inter, system-ui, sans-serif' font-weight='900' font-size='220' fill='rgba(0,0,0,0.2)'>{initials}</text>
  <text x='50%' y='68%' dominant-baseline='middle' text-anchor='middle' font-family='Inter, system-ui, sans-serif' font-weight='800' font-size='64' fill='rgba(0,0,0,0.9)'>{title}</text>
  <text x='50%' y='76%' dominant-baseline='middle' text-anchor='middle' font-family='Inter, system-ui, sans-serif' font-weight='600' font-size='24' fill='rgba(0,0,0,0.85)'>An illustrated storybook</text>
  <title>{prompt}</title>
</svg>
"""
    return _svg_data_url(svg)


def _image_prompt_for_chapter(idx: int, title: str, theme: Optional[str], setting: Optional[str], chars: List[str], style: Optional[str]) -> str:
    who = ", ".join(chars[:3]) or "a small band of friends"
    return (
        f"Illustrate chapter {idx} titled '{title}'. Show {who} in {setting or 'a cozy imaginative setting'}, "
        f"evoking {theme or 'wonder'} in a {style or 'storybook'} style. Soft lighting, warm colors, inclusive and kind."
    )


def generate_story(req: GenerateRequest) -> Story:
    chapters: List[Chapter] = []
    for i in range(1, req.chapters + 1):
        c_title = _make_chapter_title(req.title, i, req.style, req.tone)
        c_text = _chapter_text(i, req.chapters, req.theme, req.setting, req.audience, req.characters)
        c_prompt = _image_prompt_for_chapter(i, c_title, req.theme, req.setting, req.characters, req.style)
        c_svg = _chapter_image_svg(req.title, i, req.chapters, c_prompt, req.characters) if req.include_images else None
        chapters.append(
            Chapter(
                index=i,
                title=c_title,
                text=c_text,
                image_prompt=c_prompt if req.include_images else None,
                image_svg=c_svg,
            )
        )
    cover_prompt = (
        f"Illustrated cover in a cozy, luminous style. Title: '{req.title}'. "
        f"Theme: {req.theme or 'wonder'}. Setting: {req.setting or 'imaginative landscape'}. "
        f"Characters: {', '.join(req.characters) or 'a group of friends'}."
    )
    cover_svg = _cover_image_svg(req.title, cover_prompt, req.characters) if req.include_images else None
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
        cover_image_svg=cover_svg,
        generator_version="1.1-local-images",
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
