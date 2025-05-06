#!/usr/bin/env python3
"""
Slovak Audio Transcription Tool using ElevenLabs API with API Key Rotation

This script transcribes audio/video files in Slovak using ElevenLabs' Scribe API.
It saves both plain text and full JSON responses to separate files.
If one API key reaches its limit, it automatically rotates to the next available key.

Usage:
    python slovak_transcriber.py <input_file> [--output_prefix OUTPUT_PREFIX]

Requirements:
    - Python 3.6+
    - requests library
    - dotenv library (for API key management)
    
Environment Variables (.env file):
    ELEVENLABS_API_KEY_1=your_first_api_key
    ELEVENLABS_API_KEY_2=your_second_api_key
    ELEVENLABS_API_KEY_3=your_third_api_key
    ...and so on
"""

import os
import sys
import json
import re
import argparse
import requests
from pathlib import Path
from dotenv import load_dotenv


def setup_argparse():
    """Configure and parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Transcribe Slovak audio/video files using ElevenLabs API with key rotation"
    )
    
    # Create mutually exclusive group for single file vs batch mode
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "input_file", 
        nargs="?",  # Makes it optional when using batch mode
        default=None,
        help="Path to audio/video file for transcription (single file mode)"
    )
    mode_group.add_argument(
        "--batch",
        action="store_true",
        help="Enable batch processing mode for multiple files"
    )
    
    parser.add_argument(
        "--source_dir",
        help="Directory containing audio/video files for batch processing (required with --batch)"
    )
    parser.add_argument(
        "--output_prefix", 
        "-o", 
        default=None,
        help="Prefix for output files (defaults to input filename without extension)"
    )
    parser.add_argument(
        "--verbose", 
        "-v", 
        action="store_true",
        help="Enable verbose output including detailed API responses"
    )
    parser.add_argument(
        "--key",
        help="Specify which API key to use (e.g., '1', '2', 'main'). Maps to ELEVENLABS_API_KEY_X in .env"
    )
    
    return parser.parse_args()


def validate_file(file_path):
    """Validate that file exists and is accessible."""
    path = Path(file_path)
    if not path.exists():
        print(f"Error: File {file_path} does not exist.")
        sys.exit(1)
    if not path.is_file():
        print(f"Error: {file_path} is not a file.")
        sys.exit(1)
    if not os.access(file_path, os.R_OK):
        print(f"Error: No read permissions for {file_path}.")
        sys.exit(1)
    return path


def get_all_api_keys(specific_key=None):
    """Get all available API keys from environment variables in the order they appear in .env.
    
    Args:
        specific_key: If provided, only try to get the API key with this suffix.
                      E.g., '1' for ELEVENLABS_API_KEY_1, 'main' for ELEVENLABS_API_KEY_MAIN
    """
    api_keys = []
    
    # If a specific key is requested
    if specific_key:
        # Convert to uppercase for consistent handling
        specific_key = specific_key.upper()
        
        # Check for the requested key
        key_env_var = f"ELEVENLABS_API_KEY_{specific_key}"
        key = os.getenv(key_env_var)
        
        if key:
            print(f"Using specified API key: {key_env_var}")
            return [key]
        else:
            print(f"Warning: Requested API key {key_env_var} not found in environment.")
            print("Falling back to key rotation strategy.")
    
    # Get all environment variables that match our pattern
    elevenlabs_keys = {}
    for env_var, value in os.environ.items():
        # Get the default key and all keys with suffixes
        if env_var == "ELEVENLABS_API_KEY" or env_var.startswith("ELEVENLABS_API_KEY_"):
            elevenlabs_keys[env_var] = value
    
    # dotenv tends to preserve order of variables as they appear in the file
    # so we'll get the keys in the order they were defined
    for env_var, value in elevenlabs_keys.items():
        api_keys.append(value)
    
    if not api_keys:
        print("Error: No ElevenLabs API keys found in environment variables or .env file.")
        print("Please set at least one API key (ELEVENLABS_API_KEY or ELEVENLABS_API_KEY_1, ELEVENLABS_API_KEY_2, etc.)")
        sys.exit(1)
    
    # Show which keys we found (just the variable names, not the actual keys)
    key_names = list(elevenlabs_keys.keys())
    print(f"Found {len(api_keys)} API keys available for use in this order: {', '.join(key_names)}")
    
    return api_keys


def is_limit_exceeded_error(status_code, response_text):
    """Check if the error is due to usage limits being exceeded."""
    # Check for standard rate limiting status code
    if status_code == 429:
        return True
    
    # Check for specific limit-related error messages
    limit_patterns = [
        "rate limit",
        "usage limit",
        "quota exceed",
        "limit exceed",
        "credit.*exhaust",
        "exceed.*limit",
        "no.*credit"
    ]
    
    for pattern in limit_patterns:
        if re.search(pattern, response_text, re.IGNORECASE):
            return True
    
    return False


def transcribe_audio_with_rotation(file_path, specific_key=None, verbose=False):
    """Try to transcribe audio using multiple API keys with rotation on limit errors.
    
    Args:
        file_path: Path to the audio file to transcribe
        specific_key: If provided, try this specific API key first
        verbose: Whether to show verbose output
    """
    url = "https://api.elevenlabs.io/v1/speech-to-text"
    api_keys = get_all_api_keys(specific_key)
    
    # Form data including Slovak language code
    data = {
        "model_id": "scribe_v1_experimental",
        "language_code": "slk",  # ISO 639-3 code for Slovak
        "diarization": "true",  # Enable speaker identification
        "tag_audio_events": "true",  # Tag non-speech sounds
        "timestamp_granularity": "word"  # Word-level timestamps
    }
    
    last_error = None
    
    # Try each API key until one works or we run out of keys
    for i, api_key in enumerate(api_keys):
        headers = {
            "xi-api-key": api_key
        }
        
        try:
            # Open file in binary mode for each attempt
            with open(file_path, "rb") as audio_file:
                files = {
                    "file": (file_path.name, audio_file, "audio/mpeg")  # Auto-detect mime type
                }
                
                print(f"Attempt {i+1}/{len(api_keys)}: Transcribing with API key {api_key[:5]}... (Slovak language)")
                response = requests.post(url, headers=headers, files=files, data=data)
                
                # If successful, return the response JSON
                if response.status_code == 200:
                    print(f"✓ Success with API key {i+1}")
                    return response.json()
                
                # Handle API errors
                error_msg = f"API returned status code {response.status_code}"
                
                if verbose:
                    error_msg += f"\nResponse: {response.text}"
                
                # Check if this is a limit exceeded error
                if is_limit_exceeded_error(response.status_code, response.text):
                    print(f"✗ API key {i+1} has reached its usage limit. Trying next key...")
                else:
                    # For other errors, print details and continue to next key
                    print(f"✗ Error with API key {i+1}: {error_msg}")
                    
                last_error = (response.status_code, response.text)
                
        except Exception as e:
            print(f"✗ Error with API key {i+1}: {str(e)}")
            last_error = (None, str(e))
    
    # If we've tried all keys and none worked, raise the last error
    if last_error:
        status_code, error_text = last_error
        error_msg = f"All API keys failed. Last error"
        if status_code:
            error_msg += f" (status {status_code})"
        error_msg += f": {error_text}"
        raise Exception(error_msg)
    
    raise Exception("All API keys failed with unknown errors")


def process_batch(file_list, specific_key=None, verbose=False):
    """Process multiple audio files in batch mode.
    
    Args:
        file_list: List of Path objects for audio/video files
        specific_key: Optional specific API key to use
        verbose: Whether to show verbose output
        
    Returns:
        Dictionary with stats about successful and failed transcriptions
    """
    total_files = len(file_list)
    successful = []
    failed = []
    
    print(f"\n{'='*80}")
    print(f"BATCH PROCESSING: Found {total_files} audio/video files to process")
    print(f"{'='*80}\n")
    
    # Process each file
    for i, file_path in enumerate(file_list, 1):
        print(f"\n[{i}/{total_files}] Processing: {file_path.name}")
        print(f"{'-'*80}")
        
        try:
            # Get output prefix (just the filename without extension)
            output_prefix = file_path.stem
            
            # Transcribe the file
            response_json = transcribe_audio_with_rotation(
                file_path, 
                specific_key=specific_key,
                verbose=verbose
            )
            
            # Save outputs
            json_path, text_path = save_outputs(response_json, output_prefix)
            
            print(f"✓ Successfully transcribed: {file_path.name}")
            print(f"  Text saved to: {text_path}")
            print(f"  JSON saved to: {json_path}")
            
            successful.append(file_path.name)
            
        except Exception as e:
            print(f"✗ Failed to process {file_path.name}: {str(e)}")
            failed.append((file_path.name, str(e)))
    
    # Return statistics
    return {
        "total": total_files,
        "successful": successful,
        "failed": failed
    }
    
def find_audio_files(source_dir):
    """Find all audio and video files in the source directory.
    
    Args:
        source_dir: Path to directory containing audio/video files
        
    Returns:
        List of Path objects for audio/video files
    """
    # Common audio and video extensions
    audio_extensions = {
        # Audio formats
        '.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a', '.wma', '.aiff', '.opus',
        # Video formats (ElevenLabs supports video files too)
        '.mp4', '.avi', '.mov', '.wmv', '.mkv', '.webm', '.flv', '.3gp', '.m4v'
    }
    
    source_path = Path(source_dir)
    
    if not source_path.exists():
        print(f"Error: Source directory '{source_dir}' does not exist.")
        sys.exit(1)
    
    if not source_path.is_dir():
        print(f"Error: '{source_dir}' is not a directory.")
        sys.exit(1)
    
    # Find all files with audio/video extensions
    audio_files = []
    for ext in audio_extensions:
        if os.name == "nt":  # Windows (case-insensitive)
            audio_files.extend(source_path.glob(f"*{ext.lower()}"))
        else:  # Unix/Linux (case-sensitive)
            audio_files.extend(source_path.glob(f"*{ext}"))
            audio_files.extend(source_path.glob(f"*{ext.upper()}"))

    # Add deduplication as a safety measure
    audio_files = sorted(set(str(path) for path in audio_files))
    audio_files = [Path(path) for path in audio_files]
    
    if not audio_files:
        print(f"Warning: No audio or video files found in '{source_dir}'.")
        sys.exit(1)

    return audio_files

def save_outputs(response_json, output_prefix):
    """Save transcription outputs in plain text and JSON formats with organized directory structure.
    
    Args:
        response_json: The JSON response from the API
        output_prefix: Base filename without extension
        
    Returns:
        Tuple of (json_path, text_path) with the full paths to the saved files
    """
    # Create output directories if they don't exist
    output_dir = Path("output_files")
    json_dir = output_dir / "full_response"
    
    output_dir.mkdir(exist_ok=True)
    json_dir.mkdir(exist_ok=True, parents=True)
    
    # Extract just the filename without any directory parts
    base_filename = Path(output_prefix).name
    
    # Save full JSON response in output_files/full_response directory
    json_path = json_dir / f"{base_filename}.json"
    with open(json_path, "w", encoding="utf-8") as json_file:
        json.dump(response_json, json_file, ensure_ascii=False, indent=2)
    
    # Save plain text transcription in output_files directory
    text_path = output_dir / f"{base_filename}.txt"
    with open(text_path, "w", encoding="utf-8") as text_file:
        text_file.write(response_json["text"])
    
    return json_path, text_path


def main():
    """Main function to process arguments and execute transcription."""
    # Load environment variables
    load_dotenv()
    
    # Parse command line arguments
    args = setup_argparse()
    
    # Handle different processing modes
    if args.batch:
        # Batch processing mode
        if not args.source_dir:
            print("Error: --source_dir is required when using --batch mode")
            sys.exit(1)
        
        # Find all audio files in the source directory
        audio_files = find_audio_files(args.source_dir)
        
        # Process files in batch
        stats = process_batch(
            audio_files,
            specific_key=args.key,
            verbose=args.verbose
        )
        
        # Print batch processing summary
        print(f"\n{'='*80}")
        print(f"BATCH PROCESSING SUMMARY")
        print(f"{'='*80}")
        print(f"Total files processed: {stats['total']}")
        print(f"Successfully transcribed: {len(stats['successful'])}")
        print(f"Failed: {len(stats['failed'])}")
        
        if stats['failed']:
            print("\nFailed files:")
            for filename, error in stats['failed']:
                print(f"  - {filename}: {error}")
        
        print(f"\nOutput location:")
        print(f"  - Text files: output_files/")
        print(f"  - JSON files: output_files/full_response/")
        
    else:
        # Single file mode
        # Validate input file
        input_path = validate_file(args.input_file)
        
        # Set output prefix
        if args.output_prefix:
            output_prefix = args.output_prefix
        else:
            output_prefix = input_path.stem  # Filename without extension
        
        # Transcribe audio with API key rotation
        try:
            # Use the specified key if provided
            response_json = transcribe_audio_with_rotation(
                input_path, 
                specific_key=args.key,
                verbose=args.verbose
            )
            
            # Save outputs
            json_path, text_path = save_outputs(response_json, output_prefix)
            
            print(f"\nTranscription complete!")
            print(f"Plain text saved to: {text_path}")
            print(f"Full JSON response saved to: {json_path}")
            
        except Exception as e:
            print(f"Error during transcription: {str(e)}")
            sys.exit(1)


if __name__ == "__main__":
    main()