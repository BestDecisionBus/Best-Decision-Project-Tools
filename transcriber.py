import whisper

import config

_model = None


def get_model():
    """Lazy-load the Whisper model (loads once, reuses)."""
    global _model
    if _model is None:
        _model = whisper.load_model(config.WHISPER_MODEL)
    return _model


def transcribe(audio_path):
    """Transcribe an audio file. Returns the text string."""
    model = get_model()
    result = model.transcribe(str(audio_path), fp16=False)
    return result["text"].strip()
