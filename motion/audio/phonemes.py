"""The phonemes Kokoro reads for each voice-over line: the same step its
text-to-speech runs (kokoro-onnx's tokenizer, through espeak-ng, American
English), so scripts/voice.mjs can check how a word will be said, and
record it, before the voice is made.

    python audio/phonemes.py lines.json     # a JSON list of texts in, a JSON list of phonemes out
"""

import json
import sys

from kokoro_onnx.tokenizer import Tokenizer

texts = json.loads(open(sys.argv[1], encoding="utf-8").read())
tokenizer = Tokenizer()
sys.stdout.reconfigure(encoding="utf-8")
print(json.dumps([tokenizer.phonemize(text, lang="en-us") for text in texts], ensure_ascii=False))
