#!/usr/bin/env python3
"""
Quickstart Example: Place an Autonomous Outbound Call
---------------------------------------------------
Demonstrates how to dispatch a natural human-like phone call to inquire
about menu items, prices, or store availability using the 4-Pillar Human Transaction Protocol.
"""

import time
from rich.console import Console
from agentic_telephony import telephony_engine, settings

console = Console()


def main():
    console.print("[bold cyan]📞 Agentic Telephony: Outbound Calling Quickstart[/bold cyan]\n")

    # Destination phone number (E.164 format)
    target_phone = "+15551234567"
    target_business = "Luigi's Italian Kitchen"
    objective = "Ask if they have gluten-free pasta options available tonight and check the price."
    spoken_brief = (
        "1. Ask if they have gluten-free pasta tonight.\n"
        "2. If yes, ask how much it costs.\n"
        "3. Ask how long a pickup order takes.\n"
        "4. Ask them to text the pickup address to this number."
    )

    console.print(f"Dialing [bold yellow]{target_business}[/bold yellow] at [bold green]{target_phone}[/bold green]...")
    console.print(f"Provider: [bold magenta]{settings.TELEPHONY_PROVIDER.upper()}[/bold magenta]")

    try:
        # Place the call
        call = telephony_engine.place_call(
            phone_number=target_phone,
            target_name=target_business,
            objective=objective,
            spoken_brief=spoken_brief,
            category="general_inquiry",
        )

        call_id = call["call_id"]
        console.print(f"\n[bold green]✅ Call Dispatched successfully![/bold green] Call ID: [bold white]{call_id}[/bold white]")
        console.print("Monitoring call status in real-time...\n")

        # Poll status for demo
        for _ in range(5):
            time.sleep(2)
            status_info = telephony_engine.get_call_status(call_id)
            if status_info:
                console.print(f"Status: [cyan]{status_info.get('status')}[/cyan] | Turns: [yellow]{len(status_info.get('live_turns', []))}[/yellow]")
                if status_info.get("status") in ("ended", "completed"):
                    console.print("\n[bold green]Call Completed![/bold green]")
                    console.print(f"Summary: {status_info.get('summary', 'N/A')}")
                    console.print(f"Full Transcript:\n{status_info.get('transcript', '')}")
                    break

    except Exception as e:
        console.print(f"\n[bold red]❌ Call failed:[/bold red] {e}")
        console.print("[dim]Hint: Ensure your VAPI_API_KEY or RETELL_API_KEY is configured in .env[/dim]")


if __name__ == "__main__":
    main()
