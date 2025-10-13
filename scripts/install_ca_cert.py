import os
import subprocess
from pathlib import Path

import platform

def install_mitmproxy_ca_windows():
    """Install mitmproxy CA certificate in Windows certificate store."""
    mitm_dir = Path.home() / ".mitmproxy"
    ca_cert = mitm_dir / "mitmproxy-ca-cert.cer"
    
    if not ca_cert.exists():
        raise FileNotFoundError(
            f"mitmproxy CA not found at {ca_cert}. "
            "Run mitmproxy once to generate it."
        )
    
    # Install to Trusted Root Certification Authorities
    subprocess.run([
        "certutil", 
        "-addstore", 
        "-user",  # or "-enterprise" for system-wide
        "Root", 
        str(ca_cert)
    ], check=True)
    
    print(f"Installed mitmproxy CA from {ca_cert}")

def install_mitmproxy_ca_linux():
    """Install mitmproxy CA certificate in Linux certificate store."""
    mitm_dir = Path.home() / ".mitmproxy"
    ca_cert = mitm_dir / "mitmproxy-ca-cert.pem"
    
    if not ca_cert.exists():
        raise FileNotFoundError(
            f"mitmproxy CA not found at {ca_cert}. "
            "Run mitmproxy once to generate it."
        )
    
    # Copy to system CA directory
    ca_dir = Path("/usr/local/share/ca-certificates")
    ca_dir.mkdir(parents=True, exist_ok=True)
    
    dest_cert = ca_dir / "mitmproxy-ca-cert.crt"
    
    # Copy the certificate
    subprocess.run([
        "sudo", "cp", str(ca_cert), str(dest_cert)
    ], check=True)
    
    # Update CA certificates
    subprocess.run([
        "sudo", "update-ca-certificates"
    ], check=True)
    
    print(f"Installed mitmproxy CA from {ca_cert}")

def install_mitmproxy_ca():
    """Install mitmproxy CA certificate based on the current platform."""
    system = platform.system().lower()
    
    if system == "windows":
        install_mitmproxy_ca_windows()
    elif system == "linux":
        install_mitmproxy_ca_linux()
    else:
        raise NotImplementedError(f"CA installation not supported for platform: {system}")

if __name__ == "__main__":
    install_mitmproxy_ca()