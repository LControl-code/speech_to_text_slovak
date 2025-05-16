from playwright.sync_api import sync_playwright
import time
import pyperclip  # Make sure to pip install pyperclip
import os

def interact_with_claude(message, file_path=None, debug_port=9222, max_wait_time=300):
    """
    Interact with Claude.ai through an existing Chrome session.
    Sends a message, optionally uploads a file, and waits for response.
    Uses the copy button to retrieve the response.
    
    Args:
        message: Text message to send to Claude
        file_path: Path to file to upload (optional)
        debug_port: Chrome debugging port
        max_wait_time: Maximum time to wait for response in seconds
        
    Returns:
        Claude's response text from clipboard
    """
    print(f"Connecting to Chrome on debugging port {debug_port}...")
    
    with sync_playwright() as p:
        # Connect to the browser using CDP
        browser = p.chromium.connect_over_cdp(f"http://localhost:{debug_port}")
        
        # Get existing context and pages
        context = browser.contexts[0]
        pages = context.pages
        print(f"Found {len(pages)} pages in the browser")
        
        # Find Claude page
        claude_page = None
        for page in pages:
            if "claude.ai" in page.url:
                claude_page = page
                print(f"Found Claude page: {page.url}")
                break
        
        if claude_page is None:
            print("No Claude page found. Please navigate to claude.ai in your Chrome browser.")
            return None
        
        # Focus the Claude page
        claude_page.bring_to_front()
        
        # Upload file if provided
        if file_path and os.path.exists(file_path):
            try:
                print(f"Uploading file: {file_path}")
                
                # Find and click upload button
                upload_button = claude_page.locator('[data-testid="upload-button"]')
                if not upload_button.is_visible(timeout=5000):
                    # Try alternative selectors
                    upload_button = claude_page.locator('#input-plus-menu-trigger')
                
                if upload_button.is_visible():
                    upload_button.click()
                    time.sleep(1)
                    
                    # Wait for and use file input
                    with claude_page.expect_file_chooser() as fc_info:
                        claude_page.click('input[type="file"]', timeout=5000)
                    
                    file_chooser = fc_info.value
                    file_chooser.set_files(file_path)
                    
                    # Wait for file upload to complete
                    print("Waiting for file upload to complete...")
                    try:
                        claude_page.wait_for_selector('[data-testid="uploaded-file"]', timeout=30000)
                        print("✅ File uploaded successfully")
                    except:
                        print("Warning: Could not detect file upload completion marker")
                        # Still wait a bit in case the UI doesn't show the marker
                        time.sleep(5)
                else:
                    print("❌ Could not find upload button")
            except Exception as e:
                print(f"Error uploading file: {str(e)}")
        
        # Type and send the message
        try:
            print("Finding chat input area...")
            
            # Find the contenteditable div
            editable_div = claude_page.locator('div[contenteditable="true"]').first
            
            if editable_div.is_visible(timeout=5000):
                print("✅ Found contenteditable div")
                
                # Click and focus the editable area
                editable_div.click()
                
                # Clear any existing content
                claude_page.keyboard.press("Control+A")
                claude_page.keyboard.press("Backspace")
                
                # Type the message
                print(f"Typing message: {message}")
                for char in message:
                    claude_page.keyboard.type(char)
                    time.sleep(0.01)
                
                print("Message typed successfully!")
                
                # Send the message
                print("Sending message...")
                claude_page.keyboard.press("Enter")
                
                # Wait for Claude to process and respond
                print(f"Waiting for Claude's response (max {max_wait_time} seconds)...")
                
                # Wait for the copy button to appear (indicating response is ready)
                copy_button_selector = '[data-testid="action-bar-copy"]'
                try:
                    start_time = time.time()
                    copy_button_visible = False
                    
                    # Keep checking for the copy button with timeout
                    while time.time() - start_time < max_wait_time:
                        if claude_page.locator(copy_button_selector).is_visible():
                            copy_button_visible = True
                            print("✅ Response ready - copy button detected")
                            # Give a moment for response to fully render
                            time.sleep(2)
                            break
                        
                        # Print a waiting message every 10 seconds
                        if int(time.time() - start_time) % 10 == 0:
                            print(f"Still waiting for response... ({int(time.time() - start_time)}s)")
                        
                        time.sleep(1)
                    
                    if not copy_button_visible:
                        print("❌ Timed out waiting for copy button")
                        return None
                    
                    # Click the copy button to copy response to clipboard
                    print("Clicking copy button...")
                    claude_page.locator(copy_button_selector).click()
                    
                    # Give it a moment to copy to clipboard
                    time.sleep(1)
                    
                    # Get the response from clipboard
                    response = pyperclip.paste()
                    
                    if response:
                        print(f"✅ Response copied to clipboard ({len(response)} chars)")
                        return response
                    else:
                        print("❌ No response found in clipboard")
                        return None
                
                except Exception as e:
                    print(f"Error while waiting for or using copy button: {str(e)}")
                    return None
            else:
                print("❌ Could not find contenteditable div")
                return None
        
        except Exception as e:
            print(f"Error during chat interaction: {str(e)}")
            return None


if __name__ == "__main__":
    # Example usage
    prompt = "Analyze the key features of the Prague Spring movement."
    response = interact_with_claude(prompt)
    
    if response:
        # Save response to file
        with open("claude_response.txt", "w", encoding="utf-8") as f:
            f.write(response)
        print(f"Response saved to claude_response.txt")
    else:
        print("Failed to get response from Claude")