"""Render the same French passage with several voice/model combos to compare them by ear.
    .venv/bin/python scripts/voice_samples.py     -> docs/voice-samples/*.mp3
"""
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.app.config import settings  # noqa: E402

TEXT = ("Bonjour Karim, je suis Camille, l'assistante IA du recrutement du Groupe Orvane. Notre échange dure une dizaine de minutes, "
        "il est enregistré et transcrit, et c'est un recruteur qui décidera de la suite. C'est un bon moment pour vous ? "
        "Parfait, merci. Alors, pour commencer : à partir de quand pourriez-vous prendre le poste, et quel préavis devriez-vous effectuer ?")
# (file, label, voice_id, model_id, voice_settings)
COMBOS = [
    ("00-ancienne-voix-jessica-flash", "AVANT : Jessica (anglophone) + flash_v2_5", "cgSgspJ2msm6clMCkdW9", "eleven_flash_v2_5", {"stability": 0.5, "similarity_boost": 0.8}),
    ("01-emilie-v3", "Émilie (française) + eleven_v3", "d3AXX0BlgJHYFCuH9X88", "eleven_v3", {"stability": 0.5}),
    ("02-emilie-turbo25", "Émilie + turbo_v2_5", "d3AXX0BlgJHYFCuH9X88", "eleven_turbo_v2_5", {"stability": 0.4, "similarity_boost": 0.75, "style": 0.2, "speed": 1.0}),
    ("03-justine-v3", "Justine (parisienne, douce) + eleven_v3", "zPy2sgLU4pZ7Xrjh87uz", "eleven_v3", {"stability": 0.5}),
    ("04-hugo-v3", "Hugo (homme) + eleven_v3", "IbbR6Av0dWuQJS0b8JVT", "eleven_v3", {"stability": 0.5}),
]


def main():
    out = ROOT / "docs" / "voice-samples"
    out.mkdir(parents=True, exist_ok=True)
    for name, label, voice, model, vs in COMBOS:
        r = httpx.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}", params={"output_format": "mp3_44100_128"},
                       headers={"xi-api-key": settings.elevenlabs_api_key}, timeout=120,
                       json={"text": TEXT, "model_id": model, "language_code": "fr", "voice_settings": vs})
        if r.is_success:
            (out / f"{name}.mp3").write_bytes(r.content)
            print(f"OK   {name}.mp3  ({len(r.content)//1024} KB)  {label}")
        else:
            print(f"FAIL {name}: {r.status_code} {r.text[:160]}")


if __name__ == "__main__":
    main()
