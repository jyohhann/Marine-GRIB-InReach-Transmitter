import os
import json
import re
from pathlib import Path
from typing import Optional, Tuple
import requests

MISTRAL_CREDENTIALS_PATH = Path("credentials_mistral.json")
PROMPT_PATTERN = re.compile(r"Mistral:\s*(.+)", re.IGNORECASE)
LOCATION_PATTERN = re.compile(r"Lat\s*([\-0-9.]+)[ ,]*Lon\s*([\-0-9.]+)", re.IGNORECASE)
FORBIDDEN_PHRASES = ["<think>", "<system>", "<|", "<|im", "internal", "thought", "note:"]

def get_mistral_api_key() -> str:
    if not MISTRAL_CREDENTIALS_PATH.exists():
        raise RuntimeError(f"{MISTRAL_CREDENTIALS_PATH} not found at project root")
    with MISTRAL_CREDENTIALS_PATH.open() as f:
        data = json.load(f)
    key = data.get("MISTRAL_API_KEY")
    if not key:
        raise RuntimeError("MISTRAL_API_KEY not found in credentials_mistral.json")
    return key

def extract_prompt_and_location(message: str) -> Tuple[Optional[str], Optional[str]]:
    prompt_match = PROMPT_PATTERN.search(message)
    user_prompt = prompt_match.group(1).strip() if prompt_match else None

    loc_match = LOCATION_PATTERN.search(message)
    location_str = f"{loc_match.group(1)}, {loc_match.group(2)}" if loc_match else None

    return user_prompt, location_str

def augment_prompt_with_location(user_prompt: Optional[str], location_str: Optional[str]) -> Optional[str]:
    if not user_prompt or not location_str:
        return user_prompt

    patterns = [
        r"\bmy (current )?location\b",
        r"\bmy position\b",
        r"\bfrom here\b",
        r"\bfrom my coordinates\b",
        r"\bhere\b",
        r"\bI am here\b",
        r"\bI'm here\b",
        r"\bam I from\b",
        r"\bwhere am I\b",
        r"\bI'm\b",
        r"\bme\b",
        r"\bam I\b"
    ]
    pattern = re.compile("|".join(patterns), re.IGNORECASE)
    replaced = pattern.sub(location_str, user_prompt)
    return f"My current location is {location_str}. {replaced}"

def generate_mistral_response_from_inreach_message(inreach_message: str) -> str:
    user_prompt, location_str = extract_prompt_and_location(inreach_message)
    if not user_prompt:
        raise ValueError("No Mistral prompt detected in message.")

    mistral_prompt = augment_prompt_with_location(user_prompt, location_str)
    api_key = get_mistral_api_key()
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    system_prompt = (
        "You are a helpful assistant. "
        "Only reply with the direct answer to the user's question. "
        "Do not include any explanations, notes, reasoning, or meta information. "
        "Do not say 'as an AI', 'note:', or similar. "
        "If you do not know, say 'Unknown'. "
        "Never mention your limitations. "
        "Do not include internal tags such as <think>, <system>, or <end>."
    )
    data = {
        "model": "magistral-small-2506",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": mistral_prompt}
        ],
        "n": 1,
        "max_tokens": 320
    }
    try:
        response = requests.post("https://api.mistral.ai/v1/chat/completions", json=data, headers=headers)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"]
    except requests.RequestException as e:
        raise RuntimeError(f"Mistral API request failed: {e}")

def clean_llm_output(text: str) -> str:
    text = re.sub(r"<[^>]+>\n?", "", text)
    text = re.sub(r"\bend\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()

def is_valid_for_inreach(text: str) -> bool:
    return not any(f in text.lower() for f in FORBIDDEN_PHRASES)
