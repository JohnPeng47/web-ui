#!/usr/bin/env python3

import asyncio
from uuid import UUID
import click
import json

from cnc.database.session import get_session, create_db_and_tables
from cnc.database.crud import get_engagement_by_agent_id

async def run_get_engagement_by_agent_id(agent_id: str):
    """Get engagement by agent ID."""
    await create_db_and_tables()
    async for db in get_session():
        engagement = await get_engagement_by_agent_id(db, agent_id)
        if engagement:
            click.echo(f"Engagement ID: {engagement.id}")
            click.echo(f"Name: {engagement.name}")
            click.echo(f"Base URL: {engagement.base_url}")
            click.echo(f"Description: {engagement.description}")
            click.echo(f"Scopes: {engagement.scopes_data}")
            # click.echo(f"Page Data: {engagement.page_data}")

            with open("complete_page_data.json", "w") as f:
                json.dump(engagement.page_data, f)
        else:
            click.echo(f"No engagement found for agent ID: {agent_id}")
        break


@click.group()
def cli():
    """CNC Database CLI Tool"""
    pass


@cli.group()
def engagement():
    """Engagement management commands"""
    pass


@engagement.command("get-by-agent-id")
@click.argument("agent_id")
def get_engagement_by_agent_id_cmd(agent_id: str):
    """Get engagement by agent ID"""
    asyncio.run(run_get_engagement_by_agent_id(agent_id))


if __name__ == "__main__":
    cli()