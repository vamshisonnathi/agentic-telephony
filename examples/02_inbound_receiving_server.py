#!/usr/bin/env python3
"""
Quickstart Example: Run the Inbound Calling & Webhook Server
------------------------------------------------------------
Starts the FastAPI telephony server to receive inbound phone calls,
stream real-time transcripts, and capture end-of-call summaries.
"""

import uvicorn
from rich.console import Console
from agentic_telephony import settings, app

console = Console()


def main():
    host = settings.WEBHOOK_HOST
    port = settings.WEBHOOK_PORT

    console.print("[bold cyan]🚀 Agentic Telephony Webhook Server Starting...[/bold cyan]")
    console.print(f"- Listening on: [bold green]http://{host}:{port}[/bold green]")
    console.print(f"- Vapi Webhook URL: [bold yellow]http://{host}:{port}/webhook/vapi[/bold yellow]")
    console.print(f"- Retell Webhook URL: [bold yellow]http://{host}:{port}/webhook/retell[/bold yellow]")
    console.print(f"- Active Calls API: [bold white]http://{host}:{port}/api/calls/active[/bold white]")
    console.print(f"- OpenAPI Docs: [bold blue]http://{host}:{port}/docs[/bold blue]\n")
    console.print("[bold magenta]🌐 Expose to Internet for Vapi/Retell callbacks:[/bold magenta]")
    console.print("  [cyan]cloudflared tunnel --url http://localhost:8000[/cyan]")
    console.print("  [dim]or: ngrok http 8000[/dim]\n")

    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
