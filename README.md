# Slovak Audio Transcriber

![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.6+-brightgreen.svg)

A robust, production-ready transcription tool leveraging ElevenLabs' Scribe API for high-accuracy Slovak audio processing with API key rotation.

## Core Features

- **High-Accuracy Slovak Transcription**: Optimized for Slovak language using ElevenLabs' state-of-the-art Scribe model
- **Smart API Key Rotation**: Automatically rotates through multiple ElevenLabs API keys when usage limits are hit
- **Selective Key Usage**: Ability to specify which API key to use for specific tasks
- **Batch Processing**: Support for processing entire directories of audio/video files with detailed stats
- **Structured Output**: Organizes outputs with plain text in main directory and full JSON responses in subdirectory 
- **Error Resilience**: Comprehensive error handling with informative diagnostics
- **Production Ready**: Built for real-world use with industrial-grade reliability

## Quick Start

### Prerequisites

- Python 3.6+
- `requests` library
- `python-dotenv` library
- ElevenLabs API key(s)

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/slovak-transcriber.git
cd slovak-transcriber

# Set up virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install requests python-dotenv
```

### Configuration

Create a `.env` file in the project directory with your ElevenLabs API keys:

```
# Multiple keys for automatic rotation
ELEVENLABS_API_KEY_1=your_first_api_key
ELEVENLABS_API_KEY_2=your_second_api_key
ELEVENLABS_API_KEY_MAIN=your_main_api_key
```

> **Tech Note**: Key order in the `.env` file determines rotation sequence. Keys are tried in the exact order they appear.

### Usage

#### Single File Mode

```bash
# Basic transcription
python slovak_transcriber.py audio_file.mp3

# Use a specific API key
python slovak_transcriber.py audio_file.mp3 --key=1

# Specify custom output prefix
python slovak_transcriber.py audio_file.mp3 --output_prefix=meeting_transcript

# Enable verbose mode for debugging
python slovak_transcriber.py audio_file.mp3 --verbose
```

#### Batch Processing Mode

```bash
# Process all audio files in a directory
python slovak_transcriber.py --batch --source_dir=/path/to/audio/files

# Process with a specific API key
python slovak_transcriber.py --batch --source_dir=/path/to/audio/files --key=main

# Verbose batch processing
python slovak_transcriber.py --batch --source_dir=/path/to/audio/files --verbose
```

## Architecture

The transcriber follows a pragmatic design pattern optimized for reliability and clean error handling:

```
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│ Input Audio │────>│ API Rotation │────>│ Transcription │
│  (Single/   │     │ & Selection  │     │   Process     │
│   Batch)    │     └──────────────┘     └───────┬───────┘
└─────────────┘                                  │
                    ┌──────────────┐     ┌───────▼───────┐
                    │     Text     │<────┤   Structured  │
                    │   Output     │     │     Output    │
                    └──────────────┘     └───────────────┘
```

Key implementation details:

- **Dual Operation Modes**: Supports both single file and batch directory processing
- **API Key Management**: Keys from `.env` are loaded in original declaration order, ensuring deterministic rotation behavior
- **Smart Fallback**: When a specific key hits usage limits, the system gracefully falls back to rotation
- **Output Organization**: Plain text (.txt) files are stored in `output_files/` while detailed JSON responses go to `output_files/full_response/`
- **Model Selection**: Uses the `scribe_v1` model with optimized parameters for Slovak language processing
- **Error Isolation**: In batch mode, errors with individual files don't halt the entire process

## Gotchas & Troubleshooting

**API Key Exhaustion**: If all keys are exhausted, check if any free tier accounts have been reset for the month. The system will try all keys before failing.

**Missing FFmpeg**: Some audio processing may require FFmpeg. Make sure it's installed and in your PATH.

**Rate Limiting**: If you see `429` errors despite rotation, you might be hitting global IP-based rate limits. Consider adding delay between retries.

**Filename Sanitization**: The script preserves original filenames but removes path components. If you need custom output naming, use the `--output_prefix` option.

## License

MIT

## Acknowledgments

- ElevenLabs for their state-of-the-art speech-to-text API
- Contributors to the `requests` and `python-dotenv` libraries