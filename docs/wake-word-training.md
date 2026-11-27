# Training a custom wake word

LibreEcho runs microWakeWord models, small TensorFlow Lite Micro classifiers,
in place of the stock "Alexa" word. You train the model with outside tools,
then stage its folder on the device. This guide covers the exact contract the
device loads and the steps that stage it.

What this does not give you:

- LibreEcho does not train models. Training data and the training run are
  yours (section 2).
- One word runs at a time, with an optional second word. The bundled word is
  always installed; only the selection and owner folders change.
- A host score is a proxy. The device adds its own gate (section 4).
- Loading and detecting a newly trained word on the device is not verified in
  this repository. Treat your first run as an experiment and keep your backups.

## 1. What the device loads

The wake engine (`LibreEcho-UI`, `src/adapter/wake_engine_mww.cpp`) runs
TensorFlow Lite Micro with the microfrontend from TFLM. Every 10 ms of
16 kHz mono 16-bit audio becomes one feature row of 40 int8 channels (30 ms
window, 125 to 7500 Hz); every three rows, one per model, are fed to the
classifier as int8 `[1, 3, 40]`, and the classifier returns uint8 `[1, 1]`.
One probability is produced per 30 ms step, and the device compares the mean
of the last `sliding_window_size` probabilities with the cutoff.

A model is a folder named after the word, holding exactly two files:

```
<name>/<name>.tflite   the microWakeWord classifier
<name>/<name>.json     its manifest
```

The manifest is the ESPHome microWakeWord shape:

| Field | Meaning |
|---|---|
| `type` | must be `"micro"` |
| `version` | must be `2` |
| `wake_word` | the phrase sent to Home Assistant, e.g. `"Okay Nabu"` |
| `model` | the classifier file name, `<name>.tflite` |
| `micro.probability_cutoff` | window mean needed to accept |
| `micro.sliding_window_size` | probabilities averaged per score |
| `micro.feature_step_size` | audio window advance in ms (10) |
| `micro.tensor_arena_size` | bytes the interpreter may use |

Device rules, enforced before a model is accepted:

- The folder name uses 1 to 63 characters from `A-Z a-z 0-9 . _ -` and does
  not start with `.`.
- The folder holds exactly `<name>.json` and `<name>.tflite`; no third file.
  Both must be regular files, not symlinks.
- The `.tflite` must be a version 3 flatbuffer with one subgraph, an int8
  input `[1, N, 40]` and a uint8 output `[1, 1]`, and use only the 20
  operators the device resolver registers. The list mirrors
  `micro_wake_word_operators.config` in LibreEcho-Platform. Custom operators
  and any other builtin are refused.
- `tensor_arena_size` must be at most 65536 bytes. The largest bundled model
  asks for 26,080 bytes; the cap stops a corrupt manifest from exhausting the
  heap.

The shared voice-activity model is not part of your folder. The wake payload
installs it at `<root>/vad/vad.tflite` and `vad.json`, and `waked` copies it
into the owner model base the first time an owner word runs. A wake is
accepted only when the word's window mean reaches its cutoff and the VAD
window reaches 0.5.

## 2. Train the classifier (outside tools)

Use the microWakeWord training pipeline from the microWakeWord project
(`esphome/micro-wake-word`, the same project as the models LibreEcho ships).
It trains a small streaming classifier and exports a `.tflite` plus the JSON
manifest in the shape above. Your training run needs data this repository does
not provide:

- positive clips of your word, from text-to-speech, recordings, or both;
- a large set of negative clips (speech without the word, music, room noise);
- a Python environment with the training dependencies.

Keep the exported `tensor_arena_size`; the device cap above is the only limit
it is checked against. Do not train your own VAD model: reuse the bundled one.

Licensing: the bundled models are Apache-2.0. Check the licence of every data
set, TTS voice and recording you train on, and of the trained model if you
share it. Do not share recordings of other people. Recordings of your
household are personal data; keep them on your own machine.

## 3. Check the folder before staging

Copy the trained pair into `<name>/<name>.tflite` and `<name>/<name>.json`,
using the word name for both the folder and the files, and set the manifest's
`model` field to `<name>.tflite`.

The web control centre validates a model folder before it accepts or selects
it, and reports the reason when it refuses one: a missing or extra file, a
disallowed operator, a wrong tensor type or shape, a missing manifest field or
an arena over the cap. A refused model is not selected; the stock word stays
active.

The same validation runs in `waked` when it loads a selected folder. A model
that fails falls back to the stock word and the wake log says why.

## 4. Host-score clips before the device

Record clips as 16 kHz, mono, 16-bit PCM WAV. Convert other formats first.

Run the same package the repository's engine test uses, `pymicro-wakeword`
2.5.0 with `pymicro-features` 2.0.2, over your clips and your exported model:

```sh
python3 -m venv .wakeword-venv
.wakeword-venv/bin/pip install pymicro-wakeword==2.5.0

.wakeword-venv/bin/python - <<'PY'
import wave
from pymicro_wakeword import MicroWakeWord, MicroWakeWordFeatures

model = MicroWakeWord.from_config("my-word/my-word.json")
features = MicroWakeWordFeatures()
with wave.open("clips/word-01.wav", "rb") as wav:
    audio = wav.readframes(wav.getnframes())
rows = 0
for offset in range(0, len(audio), 320):  # 160 samples, 10 ms
    for feature in features.process_streaming(audio[offset:offset + 320]):
        rows += 1
        probability = model.process_streaming_prob(feature)
        if rows % model.stride == 0:
            print(f"{rows // model.stride:6d} {probability:.4f}")
PY
```

The output is one probability per 30 ms step; the device score is their mean
over `sliding_window_size`. Run the snippet over one positive clip and one
silence clip first: the positive clip's window mean should sit well above the
cutoff and the silence clip's at the model's floor.

Reading the result:

- Positive clips should cross the cutoff, from several speakers and
  distances, or the model is not learning the word.
- Negative clips (speech without the word, TV, music) should stay below it.
- The device also vetoes a wake without an active VAD window and applies a
  1.75 s cooldown after a detection. A step above the cutoff is necessary to
  wake the device, not sufficient.

## 5. Install on the device

Only the owner's device is involved, and these steps write `/data`. Make a
backup of the current configuration first.

1. Copy the model folder, unchanged, to
   `/data/libreecho/wakeword-models/<name>/` on the device. Staged models are
   excluded from configuration backups, so keep your own copy.
2. Write the folder name (only the name, no path) to
   `/data/libreecho/config/wake-model`.
3. Restart the wake service: `/etc/init.d/libreecho-waked.init restart`.
4. Check `/var/log/libreecho-waked.log`. A successful selection logs
   `using owner-staged model`. An incomplete folder, an invalid name, or a
   model the engine cannot load falls back to the stock word and the log says
   why.
5. Say the word and watch for a wake. The web "wake-word test" action is
   synthetic and does not prove real detection.

To return to the stock word, delete `/data/libreecho/config/wake-model` and
restart the service. The selection and the staged folder live on `/data`, so
they are meant to survive reboot and OTA updates. That has not been tested on
hardware yet.

The detector executable always comes from the signed wake payload. Nothing
under `/data` is executed, so a bad model cannot run code, only fail to load.

## 6. What is verified and what is not

Verified in this repository (host only):

- The device engine and the `pymicro-wakeword` reference agree on five of six
  clip comparisons to within 1/255 per step. The sixth, `alexa-twice`, differs
  by at most 8/255 on 10 of 370 steps because TFLM and the reference TFLite
  runtime round kernels differently; the model inputs are byte-identical at
  those steps.
- The store and validator tests cover a valid model, a disallowed operator,
  wrong tensor types, a missing manifest field, an arena over the cap, a
  leftover ONNX model and the folder rules above.
- The web picker, the API and the init script tests pass with the new file
  set.

Not verified here:

- A newly trained word, loaded and detected on a device. That needs your own
  training run and a hardware check.
- Device acceptance of operators outside the registered list. The validator
  refuses them on purpose.
