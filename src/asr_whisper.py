import multiprocessing as mp
from faster_whisper import WhisperModel
from src.config import WHISPER_MODEL

def asr_worker(audio_queue, text_queue):
    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="float32")

    while True:
        try:
            item = audio_queue.get(timeout=0.1)
        except:
            continue
    
        if item is None:
                break  # shutdown signal

        audio_array, sr = item
        segments, _ = model.transcribe(audio_array, language="en")
        text = " ".join(s.text.strip() for s in segments)
        text_queue.put(text)

# Global process and queues
_audio_queue = mp.Queue()
_text_queue = mp.Queue()
_asr_process = None

def start_asr():
    global _asr_process
    if _asr_process is None:
        _asr_process = mp.Process(target=asr_worker, args=(_audio_queue, _text_queue))
        _asr_process.start()

def stop_asr():
    global _asr_process
    if _asr_process is not None:
        _audio_queue.put(None)  # shutdown signal
        _asr_process.join(timeout=2)
        _asr_process.terminate()
        _asr_process = None

def transcribe(audio_array, sample_rate):
    start_asr()
    _audio_queue.put((audio_array, sample_rate))
    return _text_queue.get()
