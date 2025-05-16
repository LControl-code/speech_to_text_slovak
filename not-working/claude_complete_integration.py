#!/usr/bin/env python3
"""
Claude Automation Pipeline

A comprehensive script that handles:
1. Connecting to a running Chrome instance with Claude.ai
2. Uploading a file to Claude
3. Sending a prompt (optional)
4. Capturing Claude's response

Designed to work with Slovak transcription pipeline.
"""

from playwright.sync_api import sync_playwright
import os
import time
import argparse
import pyperclip  # For clipboard access
from pathlib import Path


def process_with_claude(file_path=None, prompt=None, debug_port=9222, max_wait_time=300):
    """
    Process a file and/or prompt with Claude and capture the response.
    
    Args:
        file_path: Path to file to upload (optional)
        prompt: Text prompt to send to Claude (optional)
        debug_port: Chrome debugging port
        max_wait_time: Maximum time to wait for Claude's response
        
    Returns:
        str: Claude's response or None if an error occurred
    """
    if file_path and not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found")
        return None
        
    if not file_path and not prompt:
        print("Error: Must provide either a file_path or prompt")
        return None
    
    # Convert file path to absolute if provided
    if file_path:
        file_path = os.path.abspath(file_path)
        print(f"Processing file: {file_path}")
    
    if prompt:
        print(f"Using prompt: {prompt}")
    
    with sync_playwright() as p:
        try:
            # Connect to existing Chrome session
            print(f"Connecting to Chrome on debugging port {debug_port}...")
            browser = p.chromium.connect_over_cdp(f"http://localhost:{debug_port}")
            
            # Get existing context and find Claude page
            context = browser.contexts[0]
            
            pages = context.pages
            print(f"Found {len(pages)} pages in the browser")
            
            claude_page = None
            for page in pages:
                if "claude.ai" in page.url:
                    claude_page = page
                    print(f"Found Claude page: {page.url}")
                    break
            
            if claude_page is None:
                print("Error: No Claude page found. Please navigate to claude.ai first")
                return None
            
            # Focus the Claude page
            claude_page.bring_to_front()
            
            # Check if we're in a chat
            if "/chat/" not in claude_page.url:
                print("Navigating to new chat...")
                claude_page.goto("https://claude.ai/new")
                time.sleep(2)
            
            # Upload file if provided
            if file_path:
                upload_success = upload_file_to_claude(claude_page, file_path)
                if not upload_success:
                    print("Error: File upload failed")
                    return None
            
            # Type prompt if provided
            if prompt:
                type_prompt(claude_page, prompt)
            
            # Send the message
            print("Sending message to Claude...")
            send_message(claude_page)
            
            # Wait for and capture response
            print(f"Waiting for Claude's response (max {max_wait_time} seconds)...")
            response = wait_for_and_copy_response(claude_page, max_wait_time)
            
            if response:
                print("\nSuccessfully received response from Claude")
                return response
            else:
                print("Failed to get response from Claude")
                return None
                
        except Exception as e:
            print(f"Error during Claude interaction: {str(e)}")
            return None


def upload_file_to_claude(page, file_path, timeout=60):
    """
    Upload a file to Claude using the page object.
    
    Args:
        page: Playwright page object
        file_path: Path to file to upload
        timeout: Maximum time to wait for upload in seconds
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # STEP 1: Click on the menu button
        print("Looking for menu trigger button...")
        menu_button = page.locator('#input-plus-menu-trigger').first
        
        if not menu_button.is_visible(timeout=5000):
            print("Menu button not found, trying alternative selector...")
            menu_button = page.locator('button[aria-label="Open attachments menu"]')
            
            if not menu_button.is_visible(timeout=3000):
                print("Error: Could not find menu button")
                return False
        
        print("Clicking menu button...")
        menu_button.click()
        time.sleep(1)  # Give menu time to appear
        
        # STEP 2: Set up file chooser expectation BEFORE clicking upload button
        with page.expect_file_chooser() as fc_info:
            # STEP 3: Click on the "Upload a file" option
            print("Looking for 'Upload a file' option...")
            
            # Try multiple selectors
            upload_button = None
            selectors = [
                'div.p-1\\.5 button:first-child',
                'button:has-text("Upload a file")',
                'button:has(svg path[d*="M6.6"])'
            ]
            
            for selector in selectors:
                try:
                    if page.locator(selector).first.is_visible(timeout=1000):
                        upload_button = page.locator(selector).first
                        print(f"Found upload button with selector: {selector}")
                        break
                except:
                    continue
            
            if not upload_button:
                print("Error: Could not find upload button in menu")
                return False
            
            print("Clicking upload button...")
            upload_button.click()
        
        # Get the file chooser from the event
        file_chooser = fc_info.value
        
        # Set the file
        print(f"Setting file: {file_path}")
        file_chooser.set_files(file_path)
        
        # Wait for upload confirmation
        print("Waiting for upload to complete...")
        
        upload_success = False
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            # Check for uploaded file indicators
            uploaded_file = page.locator('[data-testid="uploaded-file"]')
            filename_text = page.locator(f"text={os.path.basename(file_path)}")
            
            if uploaded_file.is_visible(timeout=1000) or filename_text.is_visible(timeout=1000):
                upload_success = True
                break
            
            print(f"Still waiting for upload confirmation... ({int(time.time() - start_time)}s)")
            time.sleep(2)
        
        if upload_success:
            print("✅ File uploaded successfully!")
            return True
        else:
            print("❌ Could not confirm file upload")
            return False
    
    except Exception as e:
        print(f"Error during file upload: {str(e)}")
        return False


def type_prompt(page, prompt_text):
    """
    Type a prompt into Claude's input area.
    
    Args:
        page: Playwright page object
        prompt_text: Text to type
    """
    try:
        print("Finding input area...")
        
        # Find the contenteditable div
        editable_div = page.locator('div[contenteditable="true"]').first
        
        if not editable_div.is_visible(timeout=5000):
            print("Contenteditable div not found, trying alternative selectors...")
            
            # Try alternative selectors
            input_area = page.locator('div[aria-label="Write your prompt to Claude"]')
            
            if input_area.is_visible(timeout=3000):
                editable_div = input_area
            else:
                print("Error: Could not find input area")
                return
        
        print("Clicking input area...")
        editable_div.click()
        
        # Clear any existing text
        page.keyboard.press("Control+A")
        page.keyboard.press("Backspace")
        
        # Type the prompt with human-like delays
        print("Typing prompt text...")
        for char in prompt_text:
            page.keyboard.type(char)
            time.sleep(0.01)
        
        print("Prompt typed successfully")
        
    except Exception as e:
        print(f"Error typing prompt: {str(e)}")


def send_message(page):
    """
    Send the message by pressing Enter.
    
    Args:
        page: Playwright page object
    """
    try:
        # Press Enter to send
        page.keyboard.press("Enter")
        print("Message sent")
        
        # Wait a moment for processing to start
        time.sleep(2)
        
    except Exception as e:
        print(f"Error sending message: {str(e)}")


def wait_for_and_copy_response(page, max_wait_time=300):
    """
    Wait for Claude's response and copy it using the copy button.
    
    Args:
        page: Playwright page object
        max_wait_time: Maximum time to wait in seconds
        
    Returns:
        str: Claude's response or None if timeout
    """
    try:
        # First wait for any response from Claude to appear
        print("Waiting for Claude to respond...")
        
        try:
            # Wait for a message from Claude to appear
            page.wait_for_selector('[data-message-author="claude"]', timeout=max_wait_time * 1000)
        except:
            print("Error: Timed out waiting for Claude's response to appear")
            return None
        
        # Look for completion indicator or wait until response stabilizes
        start_time = time.time()
        last_content_length = 0
        stable_count = 0
        
        while time.time() - start_time < max_wait_time:
            # Check for completion indicator
            try:
                if page.locator('[data-testid="completion-status-done"]').is_visible(timeout=1000):
                    print("Response completion indicator detected")
                    break
            except:
                pass
            
            # Check if response text has stabilized
            current_text = page.locator('[data-message-author="claude"]').last.inner_text()
            current_length = len(current_text)
            
            if current_length > 0:
                print(f"Response in progress: {current_length} chars", end="\r")
                
                if current_length == last_content_length:
                    stable_count += 1
                    if stable_count >= 5:  # Consider stable after 5 checks
                        print("\nResponse appears to have stabilized")
                        break
                else:
                    stable_count = 0
                    last_content_length = current_length
            
            time.sleep(2)
        
        # Response should be ready now - look for the copy button
        print("Looking for copy button...")
        
        # Wait a moment for UI elements to be fully available
        time.sleep(2)
        
        # Try to find the copy button
        copy_button = page.locator('[data-testid="action-bar-copy"]').first
        
        if not copy_button.is_visible(timeout=5000):
            print("Copy button not found, trying alternative selectors...")
            
            # Try an alternative selector for the copy button
            copy_button = page.locator('button:has(svg[data-testid="action-bar-copy"])')
            
            if not copy_button.is_visible(timeout=3000):
                print("Warning: Could not find copy button, trying to get text directly")
                # Fall back to getting the text directly
                response_text = page.locator('[data-message-author="claude"]').last.inner_text()
                return response_text
        
        # Click the copy button
        print("Clicking copy button...")
        copy_button.click()
        
        # Wait a moment for the clipboard to update
        time.sleep(1)
        
        # Get the response from clipboard
        response_text = pyperclip.paste()
        
        if response_text:
            print(f"Successfully copied response ({len(response_text)} chars)")
            return response_text
        else:
            print("Warning: Empty response from clipboard, falling back to direct text extraction")
            # Fall back to getting the text directly
            response_text = page.locator('[data-message-author="claude"]').last.inner_text()
            return response_text
            
    except Exception as e:
        print(f"Error capturing response: {str(e)}")
        
        # Try to get text directly as a last resort
        try:
            response_text = page.locator('[data-message-author="claude"]').last.inner_text()
            return response_text
        except:
            return None


def save_response(response, input_path, output_dir="claude_responses"):
    """
    Save Claude's response to a file.
    
    Args:
        response: Text response from Claude
        input_path: Path to the input file (for naming)
        output_dir: Directory to save responses
        
    Returns:
        str: Path to the saved response file
    """
    if not response:
        return None
    
    # Create output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    
    # Create output filename based on input file
    input_name = os.path.basename(input_path)
    base_name = os.path.splitext(input_name)[0]
    output_path = os.path.join(output_dir, f"{base_name}_analysis.txt")
    
    # Write response to file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(response)
    
    print(f"Response saved to: {output_path}")
    return output_path


def main():
    """Parse command line arguments and run the script."""
    parser = argparse.ArgumentParser(description="Process files with Claude.ai")
    parser.add_argument("--file", "-f", help="Path to file to upload to Claude")
    parser.add_argument("--prompt", "-p", help="Text prompt to send to Claude")
    parser.add_argument("--port", type=int, default=9222, help="Chrome debugging port")
    parser.add_argument("--timeout", "-t", type=int, default=300, 
                       help="Maximum time to wait for Claude's response (seconds)")
    
    args = parser.parse_args()
    
    # Validate arguments
    if not args.file and not args.prompt:
        parser.error("At least one of --file or --prompt must be provided")
    
    # Process with Claude
    response = process_with_claude(
        file_path=args.file,
        prompt=args.prompt,
        debug_port=args.port,
        max_wait_time=args.timeout
    )
    
    # Save response if we got one
    if response and args.file:
        save_response(response, args.file)
    elif response:
        # Save to a generic file if we only had a prompt
        output_dir = "claude_responses"
        os.makedirs(output_dir, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        output_path = os.path.join(output_dir, f"claude_response_{timestamp}.txt")
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(response)
        
        print(f"Response saved to: {output_path}")
    
    # Return success if we got a response
    return 0 if response else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())