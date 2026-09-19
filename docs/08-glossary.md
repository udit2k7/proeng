# 08 — Glossary

Plain-language explanations of every technical term used in these documents.
You said you're not an expert; nothing here should be a mystery.

---

**API / API key**
An API is a way for one program to ask another program for something. An API key is
a password that identifies you when you ask. Groq gives you one free.

**CPU / GPU**
The CPU is your laptop's general-purpose brain. A GPU is a specialised chip that's
much faster at the maths AI models need. Your laptop has integrated graphics
(Iris Xe) rather than a dedicated GPU, which is why local AI models will be slow —
they have to run on the CPU.

**Fallback**
When plan A doesn't work, automatically try plan B. Our rewriter falls back from
Groq → Ollama → rules without ever asking you.

**Filler words**
"Uh", "um", "like", "you know". Natural in speech, noise in a written prompt.

**Frameless window**
A window with no title bar, no minimise/maximise/close buttons — just the content.
That's how the floating panel can look like a panel rather than a program.

**Groq**
A company running AI models on custom hardware, extremely fast. They offer a free
tier. Not related to Elon Musk's "Grok" — different company, confusingly similar
name.

**Hallucination**
When an AI confidently states something untrue, or answers a question you didn't
ask. Long vague prompts make this more likely, which is the problem this tool exists
to reduce.

**Hotkey (global)**
A keyboard shortcut that works everywhere, not just inside one program. Ours is
`Ctrl+Shift+Space`.

**LLM (Large Language Model)**
The kind of AI behind Claude, ChatGPT, and Gemini. A program that predicts text.
Our rewriter uses a small one to restructure your words.

**Local / offline**
Running on your own laptop, with nothing sent over the internet. Private, free,
and usually slower.

**Ollama**
A free program that lets you download and run AI models on your own machine. Think
of it as a container for local models.

**Quantised (q4_K_M)**
A compression technique for AI models. It shrinks them by storing numbers less
precisely — roughly 4x smaller, a little less accurate, much less RAM. The "q4"
means 4-bit. Essential for running models on a laptop.

**RAM**
Your laptop's short-term memory. Programs need it while running. You have 15.7 GB
total but only 1.7 GB free, which is our tightest constraint.

**Rule-based**
Ordinary programming logic — "if the sentence starts with 'I want', it's a goal" —
rather than AI. Instant and reliable, but it can only follow rules it was given.

**SQLite**
A database that's just a single file on your disk. Used for prompt history. No
server, nothing to install.

**STT / Speech-to-text**
Converting spoken audio into written text. Also called transcription or dictation.

**Thread**
A program doing several things at once. We use separate threads so that
transcribing your voice doesn't freeze the widget while you're still talking.

**Token**
The unit AI models charge by — roughly ¾ of a word. Long prompts use more tokens,
which costs more. Reducing token waste is one of your stated goals.

**TOML**
A configuration file format designed to be readable by humans. Our `config.toml`
opens in Notepad and looks like `setting = "value"`.

**Translucent**
Partly see-through. Your panel is 75% opaque, meaning you can still read what's
behind it.

**VAD (Voice Activity Detection)**
Software that decides "is a person speaking right now, or is that just noise?"
Powers our 7-second auto-stop.

**Venv (virtual environment)**
An isolated folder holding this project's libraries, so installing something here
can't break another project on your machine.

**Whisper**
OpenAI's speech-to-text model. Free, open, runs on your own machine. The
`faster-whisper` version we use is the same model rebuilt to run about four times
faster on a CPU.
