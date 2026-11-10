"""Create (or update) the ElevenLabs interviewer agent and store ELEVENLABS_AGENT_ID in .env.

    .venv/bin/python scripts/setup_agent.py [--voice VOICE_ID] [--llm gemini-2.5-flash]
"""
import argparse
import re
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.config import settings  # noqa: E402
from backend.app.prompts import AGENT_PROMPT_TEMPLATE  # noqa: E402

API = "https://api.elevenlabs.io/v1/convai/agents"
FIRST = "{{first_message}}"
PLACEHOLDERS = {
    "job_title": "Responsable d'entrepôt logistique", "candidate_first_name": "", "language_name": "français",
    "plan": "1. Présentez-vous.", "first_message": "Bonjour, je suis Camille, l'assistante IA du recrutement du Groupe Orvane.",
}


def build(voice: str, llm: str, tts_model: str, stability: float = 0.5, speed: float = 1.0) -> dict:
    return {
        "name": "Camille — pré-entretien Orvane",
        "conversation_config": {
            "agent": {
                "first_message": FIRST,
                "language": "fr",
                "dynamic_variables": {"dynamic_variable_placeholders": PLACEHOLDERS},
                "prompt": {
                    "prompt": AGENT_PROMPT_TEMPLATE,
                    "llm": llm,
                    "temperature": 0.3,
                    "built_in_tools": {
                        "end_call": {
                            "name": "end_call",
                            "description": "Termine l'appel une fois l'entretien terminé et les au revoir dits, ou si le candidat souhaite arrêter.",
                            "params": {"system_tool_type": "end_call"},
                        }
                    },
                },
            },
            "tts": {
                "voice_id": voice, "model_id": tts_model, "stability": stability, "similarity_boost": 0.8,
                "speed": speed, "optimize_streaming_latency": 1,  # 3 (previous) trades audio quality for speed: audible "robotic" artefacts
            },
            "turn": {"turn_timeout": 10, "turn_eagerness": "patient"},
        },
        "platform_settings": {
            "auth": {"enable_auth": True},
            "overrides": {
                "conversation_config_override": {
                    "agent": {"language": True, "first_message": True},
                    "conversation": {"text_only": True},
                }
            },
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="d3AXX0BlgJHYFCuH9X88")  # Émilie: native French (France), conversational. Alternatives: zPy2sgLU4pZ7Xrjh87uz (Justine), IbbR6Av0dWuQJS0b8JVT (Hugo, male)
    ap.add_argument("--llm", default="gemini-2.5-flash")
    ap.add_argument("--tts-model", default="eleven_v3_conversational")  # expressive model made for agents; fall back: eleven_turbo_v2_5 / eleven_flash_v2_5 (fastest)
    ap.add_argument("--stability", type=float, default=0.5)
    ap.add_argument("--speed", type=float, default=1.0)
    a = ap.parse_args()
    if not settings.elevenlabs_api_key:
        sys.exit("ELEVENLABS_API_KEY manquante dans .env")
    h = {"xi-api-key": settings.elevenlabs_api_key}
    body = build(a.voice, a.llm, a.tts_model, a.stability, a.speed)
    if settings.elevenlabs_agent_id:
        r = httpx.patch(f"{API}/{settings.elevenlabs_agent_id}", headers=h, json=body, timeout=60)
        agent_id = settings.elevenlabs_agent_id
        print("update:", r.status_code)
    else:
        r = httpx.post(f"{API}/create", headers=h, json=body, timeout=60)
        print("create:", r.status_code)
        agent_id = r.json().get("agent_id") if r.is_success else None
    if not r.is_success:
        print(r.text[:1500])
        sys.exit(1)
    env = ROOT / ".env"
    txt = env.read_text()
    if re.search(r"(?m)^ELEVENLABS_AGENT_ID=.*$", txt):
        txt = re.sub(r"(?m)^ELEVENLABS_AGENT_ID=.*$", f"ELEVENLABS_AGENT_ID={agent_id}", txt)
    else:
        txt = txt.rstrip("\n") + f"\nELEVENLABS_AGENT_ID={agent_id}\n"
    env.write_text(txt)
    print("agent_id saved in .env:", agent_id)


if __name__ == "__main__":
    main()
