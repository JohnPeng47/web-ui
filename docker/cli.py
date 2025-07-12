#!/usr/bin/env python3
"""
Docker Compose Manager CLI
A tool to manage multiple docker-compose projects from a central configuration.
"""

import json
import os
import subprocess
import sys
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional

import click


class DockerComposeManager:
    """Main class for managing Docker Compose projects."""

    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from JSON file."""
        if not self.config_path.exists():
            click.echo(f"❌ Config file not found: {self.config_path}")
            click.echo("Creating example config.json...")
            self._create_example_config()
            sys.exit(1)

        try:
            with open(self.config_path, "r") as f:
                config = json.load(f)
            return config
        except json.JSONDecodeError as e:
            click.echo(f"❌ Invalid JSON in config file: {e}")
            sys.exit(1)
        except Exception as e:
            click.echo(f"❌ Error reading config file: {e}")
            sys.exit(1)

    def _create_example_config(self):
        """Create an example config.json file."""
        example_config = {
            "mattermost-docker": {
                "compose_dir": "./mattermost-docker",
                "url": "http://localhost:8065",
            },
            "jenkins-docker": {
                "compose_dir": "./jenkins-docker",
                "url": "http://localhost:8080",
            },
            "dvwa": {"compose_dir": "./dvwa", "url": "http://localhost:80"},
        }

        with open(self.config_path, "w") as f:
            json.dump(example_config, f, indent=4)

        click.echo(f"✅ Created example config at: {self.config_path}")
        click.echo("Edit this file to add your docker-compose projects.")

    def _validate_project(self, project_name: str) -> Optional[Dict[str, Any]]:
        """Validate that a project exists in config and its directory exists."""
        if project_name not in self.config:
            click.echo(f"❌ Project '{project_name}' not found in config.")
            click.echo(f"Available projects: {', '.join(self.config.keys())}")
            return None

        project_config = self.config[project_name]
        compose_dir = Path(project_config["compose_dir"]).resolve()

        if not compose_dir.exists():
            click.echo(f"❌ Compose directory not found: {compose_dir}")
            return None

        # Look for docker-compose.yml files
        compose_files = []
        for pattern in ["docker-compose*.yml", "docker-compose*.yaml"]:
            compose_files.extend([str(f) for f in compose_dir.glob(pattern)])

        if not compose_files:
            click.echo(f"❌ No docker-compose files found in: {compose_dir}")
            return None

        return {
            "name": project_name,
            "dir": compose_dir,
            "compose_files": compose_files,
        }

    def _wait_for_url(self, url: str, timeout: int = 120, interval: int = 5) -> bool:
        """Wait for a URL to become accessible."""
        if not url:
            return True  # Skip if no URL provided

        click.echo(f"🔍 Waiting for service to be ready at: {url}")
        click.echo(f"⏱️  Timeout: {timeout}s, Check interval: {interval}s")

        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                response = requests.get(url, timeout=10)
                if response.status_code < 500:  # Accept any non-server-error response
                    click.echo(f"✅ Service is ready! (HTTP {response.status_code})")
                    return True
                else:
                    click.echo(
                        f"⚠️  Service returned HTTP {response.status_code}, continuing to wait..."
                    )
            except requests.exceptions.RequestException as e:
                # Service not ready yet, continue waiting
                pass

            remaining = timeout - (time.time() - start_time)
            if remaining > 0:
                click.echo(
                    f"⏳ Service not ready yet, retrying in {interval}s... ({remaining:.0f}s remaining)"
                )
                time.sleep(interval)

        click.echo(f"❌ Service did not become ready within {timeout}s")
        return False

    def _run_docker_compose(
        self, project_info: Dict[str, Any], command: str, extra_args: list = None
    ) -> bool:
        """Run a docker compose command for a project."""
        if extra_args is None:
            extra_args = []

        compose_dir = project_info["dir"]
        project_name = project_info["name"]

        # Build the docker compose command (without -C flag for compatibility)
        cmd = ["docker", "compose", "-p", project_name, command] + extra_args

        click.echo(f"🔧 Running: {' '.join(cmd)}")
        click.echo(f"📁 Working directory: {compose_dir}")

        try:
            result = subprocess.run(cmd, check=True, cwd=str(compose_dir))
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            click.echo(f"❌ Command failed with exit code {e.returncode}")
            return False
        except FileNotFoundError:
            click.echo(
                "❌ Docker or docker compose not found. Please ensure Docker is installed."
            )
            return False

    def up(
        self, project_name: str, detach: bool = True, wait_for_ready: bool = True
    ) -> bool:
        """Bring up a docker compose project."""
        project_info = self._validate_project(project_name)
        if not project_info:
            return False

        click.echo(f"🚀 Starting project: {project_name}")

        extra_args = []
        if detach:
            extra_args.append("-d")

        success = self._run_docker_compose(project_info, "up", extra_args)

        if not success:
            click.echo(f"❌ Failed to start project '{project_name}'")
            return False

        click.echo(f"✅ Project '{project_name}' started successfully!")

        # Wait for service to be ready if URL is provided
        if wait_for_ready and detach:
            project_config = self.config[project_name]
            url = project_config.get("url")

            if url:
                if not self._wait_for_url(url):
                    click.echo(
                        f"⚠️  Project started but service at {url} is not responding"
                    )
                    return False
            else:
                click.echo(f"ℹ️  No URL configured for health check")

        return True

    def down(self, project_name: str, remove_volumes: bool = False) -> bool:
        """Bring down a docker compose project."""
        project_info = self._validate_project(project_name)
        if not project_info:
            return False

        click.echo(f"🛑 Stopping project: {project_name}")

        extra_args = []
        if remove_volumes:
            extra_args.extend(["-v"])

        success = self._run_docker_compose(project_info, "down", extra_args)

        if success:
            click.echo(f"✅ Project '{project_name}' stopped successfully!")
        else:
            click.echo(f"❌ Failed to stop project '{project_name}'")

        return success

    def list_running(self) -> Dict[str, Dict[str, Any]]:
        """List all running projects and their status."""
        running_projects = {}

        for project_name in self.config.keys():
            project_info = self._validate_project(project_name)
            if not project_info:
                continue

            # Get project status
            try:
                cmd = [
                    "docker",
                    "compose",
                    "-p",
                    project_name,
                    "ps",
                    "--format",
                    "json",
                ]

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    check=True,
                    cwd=str(project_info["dir"]),
                )

                if result.stdout.strip():
                    # Parse JSON output - handle both single JSON object and multiple lines
                    containers = []
                    stdout_lines = result.stdout.strip().split("\n")

                    for line in stdout_lines:
                        line = line.strip()
                        if not line:
                            continue

                        try:
                            container_info = json.loads(line)
                            # Handle case where container_info might be a list
                            if isinstance(container_info, list):
                                containers.extend(container_info)
                            else:
                                containers.append(container_info)
                        except json.JSONDecodeError:
                            # Fallback for older docker compose versions or non-JSON output
                            containers.append({"Name": line, "State": "unknown"})

                    if containers:
                        running_projects[project_name] = {
                            "status": "running",
                            "containers": containers,
                            "dir": str(project_info["dir"]),
                        }
                else:
                    running_projects[project_name] = {
                        "status": "stopped",
                        "containers": [],
                        "dir": str(project_info["dir"]),
                    }

            except subprocess.CalledProcessError:
                running_projects[project_name] = {
                    "status": "error",
                    "containers": [],
                    "dir": str(project_info["dir"]),
                }
            except FileNotFoundError:
                click.echo("❌ Docker or docker compose not found.")
                return {}

        return running_projects


# CLI Interface
@click.group()
@click.option("--config", "-c", default="config.json", help="Path to config.json file")
@click.pass_context
def cli(ctx, config):
    """Docker Compose Manager - Manage multiple docker-compose projects."""
    ctx.ensure_object(dict)
    ctx.obj["manager"] = DockerComposeManager(config)


@cli.command()
@click.argument("project_name")
@click.option("--no-detach", is_flag=True, help="Run in foreground (don't use -d flag)")
@click.option("--no-wait", is_flag=True, help="Don't wait for service URL to be ready")
def up(project_name, no_detach, no_wait):
    """Bring up a docker compose project."""
    manager = click.get_current_context().obj["manager"]
    success = manager.up(project_name, detach=not no_detach, wait_for_ready=not no_wait)
    sys.exit(0 if success else 1)


@cli.command()
@click.argument("project_name")
@click.option("--volumes", "-v", is_flag=True, help="Remove volumes as well")
def down(project_name, volumes):
    """Bring down a docker compose project."""
    manager = click.get_current_context().obj["manager"]
    success = manager.down(project_name, remove_volumes=volumes)
    sys.exit(0 if success else 1)


@cli.command()
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format",
)
def list(output_format):
    """List all projects and their running status."""
    manager = click.get_current_context().obj["manager"]
    projects = manager.list_running()

    if output_format == "json":
        click.echo(json.dumps(projects, indent=2))
        return

    # Table format
    if not projects:
        click.echo("No projects found.")
        return

    click.echo("📊 Docker Compose Projects Status")
    click.echo("=" * 50)

    for project_name, info in projects.items():
        status = info["status"]
        containers = info["containers"]
        directory = info["dir"]

        # Status icon
        if status == "running":
            status_icon = "🟢"
        elif status == "stopped":
            status_icon = "🔴"
        else:
            status_icon = "⚠️"

        click.echo(f"\n{status_icon} {project_name}")
        click.echo(f"   Status: {status}")
        click.echo(f"   Directory: {directory}")

        if containers:
            click.echo(f"   Containers ({len(containers)}):")
            for container in containers:
                name = container.get("Name", "Unknown")
                state = container.get("State", "Unknown")
                click.echo(f"     • {name} ({state})")
        else:
            click.echo("   Containers: None")


@cli.command()
def projects():
    """List all configured projects."""
    manager = click.get_current_context().obj["manager"]

    click.echo("📋 Configured Projects")
    click.echo("=" * 30)

    for project_name, config in manager.config.items():
        compose_dir = Path(config["compose_dir"]).resolve()
        exists = "✅" if compose_dir.exists() else "❌"

        click.echo(f"{exists} {project_name}")
        click.echo(f"   Directory: {compose_dir}")

        if compose_dir.exists():
            compose_files = []
            for pattern in ["docker-compose*.yml", "docker-compose*.yaml"]:
                compose_files.extend([str(f.name) for f in compose_dir.glob(pattern)])

            if compose_files:
                click.echo(f"   Compose files: {len(compose_files)}")
                for f in compose_files:
                    click.echo(f"     • {f}")
            else:
                click.echo("   ⚠️  No docker-compose files found")
        click.echo()


if __name__ == "__main__":
    cli()
