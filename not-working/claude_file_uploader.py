#!/usr/bin/env python3
"""
Fixed Claude File Uploader

A focused script that handles file upload to Claude's chat interface,
correctly handling the file chooser event.
"""

from playwright.sync_api import sync_playwright
import os
import time
import argparse


def upload_file_to_claude(file_path, debug_port=9222, timeout=30):
    """
    Upload a file to Claude.ai through an existing Chrome session.
    
    Args:
        file_path: Path to file to upload (must be absolute path)
        debug_port: Chrome debugging port
        timeout: Maximum time to wait for upload in seconds
        
    Returns:
        bool: True if upload was successful, False otherwise
    """
    # Convert to absolute path if not already
    file_path = os.path.abspath(file_path)
    
    if not os.path.exists(file_path):
        print(f"Error: File '{file_path}' not found")
        return False
        
    print(f"Starting file upload process for: {file_path}")
    
    with sync_playwright() as p:
        try:
            # Connect to browser
            print(f"Connecting to Chrome on port {debug_port}...")
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
                return False
            
            # Focus the Claude page
            claude_page.bring_to_front()
            
            # STEP 1: Click on the menu button
            print("Looking for menu trigger button...")
            menu_button = claude_page.locator('#input-plus-menu-trigger').first
            
            if not menu_button.is_visible(timeout=5000):
                print("Menu trigger button not found, trying alternative selectors...")
                # Try an alternative selector
                menu_button = claude_page.locator('button[aria-label="Open attachments menu"]')
                
                if not menu_button.is_visible(timeout=3000):
                    print("Error: Could not find menu trigger button")
                    return False
            
            print("Clicking menu trigger button...")
            menu_button.click()
            time.sleep(1)  # Give menu time to appear
            
            # STEP 2: Set up file chooser expectation BEFORE clicking upload button
            print("Setting up file chooser handler...")
            
            with claude_page.expect_file_chooser() as fc_info:
                # STEP 3: Click on the "Upload a file" option
                print("Looking for 'Upload a file' option in menu...")
                
                # Based on the HTML structure, try the first button in the menu
                upload_button = claude_page.locator('div.p-1\\.5 button:first-child').first
                
                if not upload_button.is_visible(timeout=3000):
                    print("First button not found, trying text-based selector...")
                    upload_button = claude_page.locator('button:has-text("Upload a file")').first
                    
                    if not upload_button.is_visible(timeout=3000):
                        print("Text selector failed, trying SVG-based selector...")
                        # Try to find by the SVG path that's unique to the upload button
                        upload_button = claude_page.locator('button:has(svg path[d*="M6.6"])').first
                        
                        if not upload_button.is_visible(timeout=3000):
                            print("Error: Could not find 'Upload a file' option")
                            return False
                
                print("Clicking 'Upload a file' option...")
                upload_button.click()
                
                # Wait for file chooser to appear (handled by the expect_file_chooser context)
                print("Waiting for file chooser...")
            
            # Get the file chooser from the event
            file_chooser = fc_info.value
            
            # Set the file path in the file chooser
            print(f"Setting file: {file_path}")
            file_chooser.set_files(file_path)
            
            # Wait for upload confirmation
            print("File selected, waiting for upload to complete...")
            upload_success = False
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                # Try multiple indicators of successful upload
                uploaded_file = claude_page.locator('[data-testid="uploaded-file"]')
                filename_text = claude_page.locator(f"text={os.path.basename(file_path)}")
                
                if uploaded_file.is_visible(timeout=1000) or filename_text.is_visible(timeout=1000):
                    upload_success = True
                    break
                
                print(f"Still waiting for upload confirmation... ({int(time.time() - start_time)}s)")
                time.sleep(2)
            
            if upload_success:
                print("✅ File uploaded successfully!")
                return True
            else:
                print("❌ Could not confirm file upload completion")
                return False
                
        except Exception as e:
            print(f"Error: {str(e)}")
            return False


def main():
    """Parse command line arguments and execute file upload."""
    parser = argparse.ArgumentParser(description="Upload a file to Claude.ai")
    parser.add_argument("file_path", help="Path to the file to upload")
    parser.add_argument("--port", type=int, default=9222, help="Chrome debugging port (default: 9222)")
    parser.add_argument("--timeout", type=int, default=30, help="Upload timeout in seconds (default: 30)")
    
    args = parser.parse_args()
    
    success = upload_file_to_claude(args.file_path, args.port, args.timeout)
    
    # Return appropriate exit code
    return 0 if success else 1


if __name__ == "__main__":
    import sys
    sys.exit(main())