#!/usr/bin/env python3
"""
Pipeline utility to transcribe Slovak audio and generate academic notes in one step.
"""

import os
import argparse
import time
from pathlib import Path
import slovak_transcriber
import transcript_processor

def process_audio_to_notes():
    """Run the full audio-to-notes pipeline with a single command."""
    parser = argparse.ArgumentParser(
        description="Process Slovak audio files to academic notes in one pipeline",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage with minimal parameters
  process -i lecture.mp3
  
  # Specify output location
  process -i lecture.mp3 -o course_notes.md
  
  # Use different Claude model
  process -i lecture.mp3 --model claude-3-opus-20240229
  
  # Use specific ElevenLabs API key
  process -i lecture.mp3 --key 2
  
  # Enable verbose output
  process -i lecture.mp3 -v

Notes:
  - Audio files should be clear recordings in Slovak language
  - Processing takes ~5-10 minutes depending on audio length
  - API keys should be configured in your .env file
  - Output is in Markdown format with academic structure
"""
    )
    
    input_group = parser.add_argument_group('Input options')
    input_group.add_argument(
        "--input", "-i", required=True, 
        help="Path to Slovak audio file (MP3, WAV, M4A supported)"
    )
    
    output_group = parser.add_argument_group('Output options')
    output_group.add_argument(
        "--output", "-o", 
        help="Output markdown file path (default: notes_[audio_filename].md)"
    )
    
    model_group = parser.add_argument_group('Model configuration')
    model_group.add_argument(
        "--model", default="claude-3-7-sonnet-20250219",
        help="Claude model for notes generation (default: claude-3-7-sonnet-20250219)"
    )
    model_group.add_argument(
        "--key", 
        help="ElevenLabs API key index from .env (e.g., '1', '2', 'main')"
    )
    
    debug_group = parser.add_argument_group('Debugging')
    debug_group.add_argument(
        "--verbose", "-v", action="store_true",
        help="Enable verbose output for debugging"
    )
    debug_group.add_argument(
        "--keep-temp", action="store_true",
        help="Keep temporary files after processing"
    )
    
    args = parser.parse_args()
    
    # Print pipeline header
    print("\n" + "=" * 80)
    print(f"🚀 SPEECH-TO-NOTES PIPELINE: {Path(args.input).name}")
    print("=" * 80)
    
    # The rest of your implementation goes here
    # (Keeping your existing implementation)
    
    # 1. First transcribe the audio file
    print(f"🎙️ STEP 1/2: Transcribing audio file: {args.input}")
    
    # Prepare args for transcription
    transcribe_args = type('Args', (), {
        'input_file': args.input,
        'batch': False,
        'source_dir': None,
        'output_prefix': None,
        'verbose': args.verbose,
        'key': args.key
    })
    
    # Call transcriber with our custom args object
    try:
        slovak_transcriber.main(args=transcribe_args)
        
        # 2. Find the generated transcript
        transcript_dir = Path("output_files")
        transcript_file = transcript_dir / f"{Path(args.input).stem}.txt"
        
        if not transcript_file.exists():
            raise FileNotFoundError(f"Transcription file not found: {transcript_file}")
        
        print(f"✅ Transcription complete: {transcript_file}")
        time.sleep(1)  # Ensure file is fully written
        
        # 3. Generate notes from the transcript
        print(f"\n📝 STEP 2/2: Generating academic notes from transcript...")
        
        output_file = args.output
        if not output_file:
            output_file = f"notes_{Path(args.input).stem}.md"
        
        # Prepare config for notes generation
        config = {
            "model": args.model,
            "temperature": 1.0,
            "max_tokens": 20000,
        }
        
        processor = transcript_processor.TranscriptProcessor(config)
        transcript_text = processor.read_transcript(str(transcript_file))
        processor.process_transcript(transcript_text, output_file)
        
        # Clean up temp files if needed
        if not args.keep_temp and not args.verbose:
            # Consider cleaning up intermediate files
            pass
            
        print("\n" + "=" * 80)
        print(f"✨ PIPELINE COMPLETE: Generated notes saved to {output_file}")
        print("=" * 80 + "\n")
        
    except Exception as e:
        print(f"\n❌ Pipeline error: {str(e)}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return 1
    
    return 0

if __name__ == "__main__":
    process_audio_to_notes()