#!/usr/bin/env python3

import asyncio
from uuid import UUID
import click
import json

from cnc.database.session import get_session, create_db_and_tables
from cnc.database.crud import get_engagement_by_agent_id, update_engagement
from cnc.schemas.engagement import EngagementUpdate

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

async def run_update_engagement(engagement_id: str, name: str = None, description: str = None):
    """Update an engagement."""
    await create_db_and_tables()
    async for db in get_session():
        try:
            update_data = EngagementUpdate()
            
            if name:
                update_data.name = name
            if description:
                update_data.description = description
                
            updated_engagement = await update_engagement(db, UUID(engagement_id), update_data)
            
            click.echo(f"Updated engagement:")
            click.echo(f"ID: {updated_engagement.id}")
            click.echo(f"Name: {updated_engagement.name}")
            click.echo(f"Description: {updated_engagement.description}")
            
        except ValueError as e:
            click.echo(f"Error: {e}")
        except Exception as e:
            click.echo(f"Unexpected error: {e}")
        break


async def run_get_agent_steps(agent_id: str, reflection: bool = False, script: bool = False, output: bool = False):
    """Get agent steps by agent ID."""
    await create_db_and_tables()
    async for db in get_session():
        try:
            from cnc.database.agent.crud import get_agent_steps
            
            steps = await get_agent_steps(db, agent_id)
            
            if steps:
                click.echo(f"Found {len(steps)} steps for agent {agent_id}:")
                for i, step in enumerate(steps, 1):
                    click.echo(f"Step {i}:")
                    click.echo(f"  Step Number: {step.step_num}")
                    
                    # If no flags are provided, show reflection by default
                    if not reflection and not script and not output:
                        click.echo(f"  Reflection: {step.reflection}")
                    else:
                        # Show only the requested parts
                        if reflection:
                            click.echo(f"  Reflection: {step.reflection}")
                        if script:
                            click.echo(f"  Script: {step.script}")
                        if output and step.execution_output:
                            click.echo(f"  Output: {step.execution_output}")
                    click.echo()
            else:
                click.echo(f"No steps found for agent ID: {agent_id}")
                
        except ValueError as e:
            click.echo(f"Error: {e}")
        except Exception as e:
            click.echo(f"Unexpected error: {e}")
        break


@click.group()
def cli():
    """CNC Database CLI Tool"""
    pass


@cli.group()
def engagement():
    """Engagement management commands"""
    pass


@cli.group()
def agent():
    """Agent management commands"""
    pass


@engagement.command("get-by-agent-id")
@click.argument("agent_id")
def get_engagement_by_agent_id_cmd(agent_id: str):
    """Get engagement by agent ID"""
    asyncio.run(run_get_engagement_by_agent_id(agent_id))


@engagement.command("update")
@click.argument("engagement_id")
@click.option("--name", help="New name for the engagement")
@click.option("--description", help="New description for the engagement")
def update_engagement_cmd(engagement_id: str, name: str = None, description: str = None):
    """Update an engagement"""
    asyncio.run(run_update_engagement(engagement_id, name, description))


@agent.command("get-steps")
@click.argument("agent_id")
@click.option("--reflection", is_flag=True, help="Show reflection text")
@click.option("--script", is_flag=True, help="Show script text")
@click.option("--output", is_flag=True, help="Show execution output")
def get_agent_steps_cmd(agent_id: str, reflection: bool, script: bool, output: bool):
    """Get agent steps by agent ID"""
    asyncio.run(run_get_agent_steps(agent_id, reflection, script, output))

if __name__ == "__main__":
    cli()