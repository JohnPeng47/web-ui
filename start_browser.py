#!/usr/bin/env python3
"""
Chrome CDP Server - Launch Chrome/Chromium with remote debugging enabled

This script launches a Chrome/Chromium instance with Chrome DevTools Protocol (CDP)
enabled for remote control over the network.
"""

import argparse
import subprocess
import sys
import time
import requests
import signal
import os
from pathlib import Path


class ChromeCDPServer:
    def __init__(self, chrome_path, port=9222, address="0.0.0.0", user_data_dir=None):
        self.chrome_path = Path(chrome_path)
        self.port = port
        self.address = address
        # Use Windows-appropriate temp directory
        temp_dir = os.environ.get('TEMP', '/tmp') if os.name == 'nt' else '/tmp'
        self.user_data_dir = user_data_dir or f"{temp_dir}/chrome-cdp-{port}"
        self.process = None
        
    def validate_chrome_path(self):
        """Validate that the Chrome executable exists and is executable."""
        if not self.chrome_path.exists():
            raise FileNotFoundError(f"Chrome executable not found: {self.chrome_path}")
        
        if not self.chrome_path.is_file():
            raise ValueError(f"Chrome path is not a file: {self.chrome_path}")
            
        # Check if executable (on Unix-like systems)
        if hasattr(os, 'access') and not os.access(self.chrome_path, os.X_OK):
            raise PermissionError(f"Chrome executable is not executable: {self.chrome_path}")
    
    def build_command(self):
        """Build the Chrome command with CDP flags."""
        command = [
            str(self.chrome_path),
            f"--remote-debugging-port={self.port}",
            f"--remote-debugging-address={self.address}",
            "--remote-allow-origins=*",
            f"--user-data-dir={self.user_data_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-dev-shm-usage",
            "--no-sandbox",  # Note: Only use in controlled environments
        ]
        return command
    
    def start(self):
        """Start the Chrome instance with CDP enabled."""
        try:
            self.validate_chrome_path()
            
            print(f"Starting Chrome CDP server...")
            print(f"Chrome path: {self.chrome_path}")
            print(f"CDP endpoint: http://{self.address}:{self.port}")
            print(f"User data dir: {self.user_data_dir}")
            
            command = self.build_command()
            
            # Start Chrome process
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid if hasattr(os, 'setsid') else None
            )
            
            # Wait a moment for Chrome to start
            time.sleep(3)
            
            # Check if process is still running
            if self.process.poll() is not None:
                stdout, stderr = self.process.communicate()
                print(f"Chrome failed to start!")
                print(f"STDOUT: {stdout.decode()}")
                print(f"STDERR: {stderr.decode()}")
                return False
            
            # Test CDP connection
            if self.test_connection():
                test_address = "127.0.0.1" if self.address == "0.0.0.0" else self.address
                print(f"✅ Chrome CDP server started successfully!")
                print(f"📡 CDP API: http://{test_address}:{self.port}/json")
                print(f"🔍 DevTools: http://{test_address}:{self.port}")
                return True
            else:
                print("❌ Failed to connect to CDP endpoint")
                self.stop()
                return False
                
        except Exception as e:
            print(f"Error starting Chrome: {e}")
            return False
    
    def test_connection(self, timeout=10):
        """Test if CDP endpoint is accessible."""
        try:
            # Use localhost for testing instead of bind address
            test_address = "127.0.0.1" if self.address == "0.0.0.0" else self.address
            url = f"http://{test_address}:{self.port}/json/version"
            response = requests.get(url, timeout=timeout)
            if response.status_code == 200:
                version_info = response.json()
                print(f"Chrome version: {version_info.get('Browser', 'Unknown')}")
                return True
        except requests.RequestException as e:
            print(f"Connection test failed: {e}")
        return False
    
    def stop(self):
        """Stop the Chrome process."""
        if self.process:
            try:
                # Try graceful shutdown first
                self.process.terminate()
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Force kill if graceful shutdown fails
                self.process.kill()
                self.process.wait()
            except Exception as e:
                print(f"Error stopping Chrome: {e}")
            finally:
                self.process = None
                print("Chrome CDP server stopped.")
    
    def run_interactive(self):
        """Run the server and wait for user input to stop."""
        if self.start():
            try:
                print("\n" + "="*50)
                print("Chrome CDP Server is running!")
                print("Press Ctrl+C to stop the server")
                print("="*50)
                
                # Keep the script running
                while True:
                    time.sleep(1)
                    
            except KeyboardInterrupt:
                print("\n\nShutting down...")
            finally:
                self.stop()
        else:
            sys.exit(1)


def find_chrome_executable():
    """Try to find Chrome/Chromium executable in common locations."""
    common_paths = [
        # Linux
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/snap/bin/chromium",
        # macOS
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Chromium.app/Contents/MacOS/Chromium",
        # Windows (if running under WSL or similar)
        "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe",
        "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe",
    ]
    
    for path in common_paths:
        if Path(path).exists():
            return path
    
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Launch Chrome/Chromium with CDP remote debugging enabled",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --port 9222 --chrome /usr/bin/google-chrome
  %(prog)s -p 9223 -c /usr/bin/chromium --address 192.168.1.100
  %(prog)s --port 9222  # Auto-detect Chrome location
        """
    )
    
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=9222,
        help="Port for CDP remote debugging (default: 9222)"
    )
    
    parser.add_argument(
        "-c", "--chrome",
        type=str,
        default=r"C:\Users\jpeng\AppData\Local\ms-playwright\chromium-1161\chrome-win\chrome.exe",
        help="Path to Chrome/Chromium executable (auto-detect if not specified)"
    )
    
    parser.add_argument(
        "-a", "--address",
        type=str,
        default="0.0.0.0",
        help="Address to bind CDP server (default: 0.0.0.0 for all interfaces)"
    )
    
    parser.add_argument(
        "--user-data-dir",
        type=str,
        help="Custom user data directory (default: /tmp/chrome-cdp-{port})"
    )
    
    parser.add_argument(
        "--test-only",
        action="store_true",
        help="Start Chrome, test connection, and exit immediately"
    )
    
    args = parser.parse_args()
    
    # Find Chrome executable
    chrome_path = args.chrome
    if not chrome_path:
        chrome_path = find_chrome_executable()
        if not chrome_path:
            print("❌ Could not find Chrome/Chromium executable!")
            print("Please specify the path using --chrome option")
            print("\nCommon locations:")
            print("  Linux: /usr/bin/google-chrome, /usr/bin/chromium")
            print("  macOS: /Applications/Google Chrome.app/Contents/MacOS/Google Chrome")
            print("  Windows: C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe")
            sys.exit(1)
    
    # Create and run CDP server
    server = ChromeCDPServer(
        chrome_path=chrome_path,
        port=args.port,
        address=args.address,
        user_data_dir=args.user_data_dir
    )
    
    if args.test_only:
        if server.start():
            print("✅ Test successful!")
            server.stop()
            sys.exit(0)
        else:
            print("❌ Test failed!")
            sys.exit(1)
    else:
        server.run_interactive()


if __name__ == "__main__":
    main()