#!/usr/bin/env python3
"""
Multi-Agent Example: Autonomous Phone Errand with CrewAI
-------------------------------------------------------
Demonstrates wiring the autonomous telephony tools into a CrewAI Agent
to research, dial, verify, and report back call results.
"""

from rich.console import Console
from agentic_telephony import PhoneCallingAgent

console = Console()


def main():
    console.print("[bold cyan]🤖 Agentic Telephony with CrewAI Specialist Agent[/bold cyan]\n")

    # Instantiate the agent
    agent_wrapper = PhoneCallingAgent(caller_name="Alex")
    console.print(f"Role: [bold yellow]{agent_wrapper.role}[/bold yellow]")
    console.print(f"Tools equipped: [bold green]{[t.name for t in agent_wrapper.tools]}[/bold green]\n")

    try:
        from crewai import Task, Crew

        crew_agent = agent_wrapper.as_crewai_agent()

        task = Task(
            description=(
                "Call 'Sunny Days Party Rentals' at '+15551234567'. "
                "Ask if they have 20 folding chairs and 2 banquet tables available for this Saturday. "
                "Inquire about total cost and pickup times. "
                "Report a clean summary of what they said."
            ),
            expected_output="A bulleted summary of item availability, prices, and pickup instructions from the vendor.",
            agent=crew_agent,
        )

        crew = Crew(
            agents=[crew_agent],
            tasks=[task],
            verbose=True,
        )

        console.print("[dim]Starting CrewAI autonomous execution...[/dim]")
        result = crew.kickoff()
        console.print(f"\n[bold green]Final Result:[/bold green]\n{result}")

    except ImportError:
        console.print("[yellow]⚠️ CrewAI not installed. Install with 'pip install crewai' to run this workflow.[/yellow]")
        console.print("The phone calling tools also work standalone with any Python framework or script.")


if __name__ == "__main__":
    main()
