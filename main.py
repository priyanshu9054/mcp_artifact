import json
import os
from pathlib import Path
from urllib.parse import urlparse
from dotenv import load_dotenv
from fastmcp import FastMCP
from fastmcp.server.auth.providers.google import GoogleProvider

# Load environment variables from .env file
load_dotenv()

# Strategy to load Google OAuth credentials:
# 1. Look for a local client.json file
# 2. Look for CLIENT_CREDS JSON string in the environment
# 3. Look for individual GOOGLE_* environment variables

client_id = None
client_secret = None
redirect_uri = None

client_json_path = Path("client.json")
if client_json_path.exists():
    try:
        with open(client_json_path, "r") as f:
            data = json.load(f)
            # Handle standard Google client secret JSON structure (wraps keys inside "web" or "installed")
            if "web" in data:
                creds = data["web"]
            elif "installed" in data:
                creds = data["installed"]
            else:
                creds = data
            
            client_id = creds.get("client_id")
            client_secret = creds.get("client_secret")
            if creds.get("redirect_uris"):
                redirect_uri = creds["redirect_uris"][0]
    except Exception as e:
        print(f"Error loading client.json: {e}")

# If not loaded from client.json, try CLIENT_CREDS environment variable
if not client_id and os.getenv("CLIENT_CREDS"):
    try:
        creds = json.loads(os.getenv("CLIENT_CREDS"))
        client_id = creds.get("client_id")
        client_secret = creds.get("client_secret")
        if creds.get("redirect_uris"):
            redirect_uri = creds["redirect_uris"][0]
    except Exception as e:
        print(f"Error parsing CLIENT_CREDS: {e}")

# If still not loaded, try individual environment variables
if not client_id:
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")

if not client_id:
    raise ValueError(
        "Google OAuth Client ID is not configured. "
        "Please provide client.json or set GOOGLE_CLIENT_ID / CLIENT_CREDS in your .env file."
    )

# Parse redirect URI to automatically extract base_url and redirect_path
if redirect_uri:
    parsed_url = urlparse(redirect_uri)
    base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
    redirect_path = parsed_url.path
else:
    base_url = "http://localhost:8000"
    redirect_path = "/auth/callback"

# The GoogleProvider handles Google's token format and validation
auth_provider = GoogleProvider(
    client_id=client_id,
    client_secret=client_secret,
    base_url=base_url,
    redirect_path=redirect_path,
    required_scopes=[                                  # Request user information
        "openid",
        "https://www.googleapis.com/auth/userinfo.email",
    ],
)

mcp = FastMCP(name="Artifact-MCP", auth=auth_provider)

# Add a protected tool to test authentication
@mcp.tool
async def get_user_info() -> dict:
    """Returns information about the authenticated Google user."""
    from fastmcp.server.dependencies import get_access_token
    
    token = get_access_token()
    # The GoogleProvider stores user data in token claims
    return {
        "google_id": token.claims.get("sub"),
        "email": token.claims.get("email"),
        "name": token.claims.get("name"),
        "picture": token.claims.get("picture"),
        "locale": token.claims.get("locale")
    }

@mcp.tool
def add(a: int, b: int) -> int:
    """Add two numbers"""
    return a + b


if __name__ == "__main__":
    # Support specifying transport via environment variable (default to "sse" as requested)
    transport = os.getenv("FASTMCP_TRANSPORT", "sse")
    
    # Host and port configuration
    host = os.getenv("FASTMCP_HOST", "127.0.0.1")
    port = int(os.getenv("FASTMCP_PORT", "8000"))
    
    print(f"Starting FastMCP server with transport: '{transport}' on http://{host}:{port}")
    mcp.run(transport=transport, host=host, port=port)
 