#!/usr/bin/env python3

import asyncio
from uuid import UUID
import click
import json
from typing import Optional

from cnc.database.session import get_session, create_db_and_tables
from cnc.database.crud import get_engagement_by_agent_id, update_engagement, list_agents_for_engagement, get_engagement, delete_all_agents_for_engagement
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

async def run_update_engagement(engagement_id: str, name: Optional[str] = None, description: Optional[str] = None):
    """Update an engagement."""
    await create_db_and_tables()
    async for db in get_session():
        try:
            update_data = EngagementUpdate()
            
            if name:
                update_data.name = name
            if description:
                update_data.description = description
                
            updated_engagement = await update_engagement(db, engagement_id, update_data)
            
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


async def run_list_agents_for_engagement(engagement_id: str, agent_type: Optional[str] = None):
    """List all agents for an engagement."""
    await create_db_and_tables()
    async for db in get_session():
        try:
            # First verify the engagement exists
            engagement = await get_engagement(db, UUID(engagement_id))
            if not engagement:
                click.echo(f"No engagement found with ID: {engagement_id}")
                return
            
            agents = await list_agents_for_engagement(db, UUID(engagement_id), agent_type)
            
            if agents:
                click.echo(f"Found {len(agents)} agents for engagement {engagement_id}:")
                for agent in agents:
                    click.echo(f"  Agent ID: {agent.id}")
                    click.echo(f"  Type: {agent.agent_type}")
                    click.echo(f"  Status: {agent.agent_status}")
                    click.echo(f"  Complete Data: {agent.complete_data if hasattr(agent, 'complete_data') else {}}")
                    # Only ExploitAgentModel has vulnerability_title
                    try:
                        from cnc.database.agent.models import ExploitAgentModel
                        if isinstance(agent, ExploitAgentModel):
                            click.echo(f"  Vulnerability Title: {agent.vulnerability_title}")
                    except Exception:
                        pass
                    if hasattr(agent, "created_at"):
                        click.echo(f"  Created: {agent.created_at}")
                    click.echo()
            else:
                filter_text = f" of type '{agent_type}'" if agent_type else ""
                click.echo(f"No agents{filter_text} found for engagement ID: {engagement_id}")
                
        except ValueError as e:
            click.echo(f"Error: {e}")
        except Exception as e:
            click.echo(f"Unexpected error: {e}")
        break


async def run_delete_agent(agent_id: str):
    """Delete a single agent by ID."""
    await create_db_and_tables()
    async for db in get_session():
        try:
            from cnc.database.agent.crud import delete_agent

            deleted = await delete_agent(db, agent_id)
            assert deleted is not None
            click.echo(f"Deleted agent {agent_id} ({deleted.agent_type})")
        except ValueError as e:
            click.echo(f"Error: {e}")
        except Exception as e:
            click.echo(f"Unexpected error: {e}")
        break


async def run_delete_all_agents_for_engagement(engagement_id: str, agent_type: Optional[str] = None):
    """Delete all agents for an engagement, optionally filtered by type."""
    await create_db_and_tables()
    async for db in get_session():
        try:
            engagement = await get_engagement(db, UUID(engagement_id))
            if not engagement:
                click.echo(f"No engagement found with ID: {engagement_id}")
                return

            count = await delete_all_agents_for_engagement(db, UUID(engagement_id), agent_type)
            filter_text = f" of type '{agent_type}'" if agent_type else ""
            click.echo(f"Deleted {count} agents{filter_text} for engagement {engagement_id}")
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
def update_engagement_cmd(engagement_id: str, name: Optional[str] = None, description: Optional[str] = None):
    """Update an engagement"""
    asyncio.run(run_update_engagement(engagement_id, name, description))


@engagement.command("list-agents")
@click.argument("engagement_id")
@click.option("--type", "agent_type", type=click.Choice(["exploit", "discovery"]), help="Filter by agent type")
def list_agents_for_engagement_cmd(engagement_id: str, agent_type: Optional[str] = None):
    """List all agents for an engagement"""
    asyncio.run(run_list_agents_for_engagement(engagement_id, agent_type))


@agent.command("get-steps")
@click.argument("agent_id")
@click.option("--reflection", is_flag=True, help="Show reflection text")
@click.option("--script", is_flag=True, help="Show script text")
@click.option("--output", is_flag=True, help="Show execution output")
def get_agent_steps_cmd(agent_id: str, reflection: bool, script: bool, output: bool):
    """Get agent steps by agent ID"""
    asyncio.run(run_get_agent_steps(agent_id, reflection, script, output))


@agent.command("delete")
@click.argument("agent_id")
def delete_agent_cmd(agent_id: str):
    """Delete a single agent by ID"""
    asyncio.run(run_delete_agent(agent_id))


@engagement.command("delete-agents")
@click.argument("engagement_id")
@click.option("--type", "agent_type", type=click.Choice(["exploit", "discovery"]))
def delete_all_agents_for_engagement_cmd(engagement_id: str, agent_type: Optional[str] = None):
    """Delete all agents for an engagement (optionally filtered by type)"""
    asyncio.run(run_delete_all_agents_for_engagement(engagement_id, agent_type))

if __name__ == "__main__":
    cli()