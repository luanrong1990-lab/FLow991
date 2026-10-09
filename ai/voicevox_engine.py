import os
import aiohttp
import urllib.request
import json
from utils.logger import app_logger
from config.config_manager import load_settings

class VoicevoxTTS:
    def __init__(self):
        settings = load_settings()
        self.url = settings.get("VOICEVOX_URL", "http://127.0.0.1:50021")
        self.speaker = settings.get("VOICEVOX_SPEAKER", 3) # 3 = Zundamon Normal

    def check_health(self) -> bool:
        try:
            req = urllib.request.Request(f"{self.url}/version", method="GET")
            with urllib.request.urlopen(req, timeout=3) as response:
                return response.status == 200
        except Exception as e:
            app_logger.error(f"Voicevox health check failed: {e}")
            return False

    async def generate_audio(self, text: str, output_path: str, speaker_id: int = None) -> bool:
        if speaker_id is None:
            speaker_id = self.speaker
            
        try:
            async with aiohttp.ClientSession() as session:
                # 1. Audio Query
                params = {"text": text, "speaker": speaker_id}
                async with session.post(f"{self.url}/audio_query", params=params) as resp:
                    if resp.status != 200:
                        app_logger.error(f"Voicevox audio_query failed: {resp.status}")
                        return False
                    query = await resp.json()
                    
                # 2. Synthesis
                params = {"speaker": speaker_id}
                async with session.post(f"{self.url}/synthesis", params=params, json=query) as resp:
                    if resp.status != 200:
                        app_logger.error(f"Voicevox synthesis failed: {resp.status}")
                        return False
                    audio_data = await resp.read()
                    
            with open(output_path, "wb") as f:
                f.write(audio_data)
                
            return True
            
        except Exception as e:
            app_logger.error(f"Voicevox generation error: {e}")
            return False
