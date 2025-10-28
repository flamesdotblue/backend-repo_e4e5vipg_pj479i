"""
Database Schemas for the AI Storybook Generator

Each Pydantic model corresponds to a MongoDB collection (lowercased class name).
"""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Optional

class Chapter(BaseModel):
    index: int = Field(..., ge=1, description="Chapter number starting at 1")
    title: str = Field(..., description="Chapter title")
    text: str = Field(..., description="Chapter content text")
    image_prompt: Optional[str] = Field(None, description="Prompt describing the illustration for this chapter")
    image_svg: Optional[str] = Field(None, description="Inline SVG data URL representing the chapter illustration")

class Story(BaseModel):
    title: str = Field(..., description="Story title")
    theme: Optional[str] = Field(None, description="Core theme or prompt of the story")
    audience: str = Field("children", description="Target audience, e.g., children, teens, adults")
    style: Optional[str] = Field(None, description="Writing style, e.g., fairy tale, sci-fi, whimsical")
    tone: Optional[str] = Field(None, description="Tone like cozy, adventurous, epic")
    moral: Optional[str] = Field(None, description="Moral or lesson of the story")
    setting: Optional[str] = Field(None, description="Primary setting of the story")
    language: str = Field("en", description="ISO language code for output language")
    characters: List[str] = Field(default_factory=list, description="Key character names")
    chapters: List[Chapter] = Field(default_factory=list, description="List of chapters")
    cover_prompt: Optional[str] = Field(None, description="Prompt for cover art generation (optional)")
    cover_image_svg: Optional[str] = Field(None, description="Inline SVG data URL for cover art")
    generator_version: str = Field("1.1-images-local", description="Local generator version tag")
