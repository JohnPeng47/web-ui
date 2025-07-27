#!/usr/bin/env python3
"""
check_docker_repos.py

Verify the existence of Docker Hub repositories for a curated set of web apps.
Uses the v2 API at:
  https://registry.hub.docker.com/v2/repositories/{namespace}/{name}/tags

Requires: docker.py (from the earlier message) in the same directory.

Usage:
    python check_docker_repos.py
    python check_docker_repos.py --tags 5 --timeout 20
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Tuple

from docker import repository_exists, list_tags


import csv

# Project name, Docker Hub repository, and OSV search term mapping
PROJECT_REPOS: List[Tuple[str, str, str]] = [
    ("MediaWiki", "library/mediawiki", "mediawiki/core:Packagist"),
    ("Drupal", "library/drupal", "drupal/core:Packagist"),
    ("Joomla", "library/joomla", "joomla/joomla-cms:Packagist"),
    ("Matomo", "library/matomo", "matomo/matomo:Packagist"),
    ("Ghost", "library/ghost", "ghost:npm"),
    ("Grafana", "grafana/grafana", "github.com/grafana/grafana:Go"),
    ("Prometheus", "prom/prometheus", "github.com/prometheus/prometheus:Go"),
    ("Mattermost", "mattermost/mattermost-team-edition", "github.com/mattermost/mattermost-server:Go"),
    ("Gitea", "gitea/gitea", "code.gitea.io/gitea:Go"),
    ("Harbor", "goharbor/harbor", "github.com/goharbor/harbor:Go"),
    ("Portainer", "portainer/portainer-ce", "github.com/portainer/portainer:Go"),
    ("MinIO", "minio/minio", "github.com/minio/minio:Go"),
    ("Sentry", "getsentry/sentry", "sentry:PyPI"),
    ("NetBox", "netboxcommunity/netbox", "netbox:PyPI"),
    ("Apache Superset", "apache/superset", "apache-superset:PyPI"),
    ("Apache Airflow", "apache/airflow", "apache-airflow:PyPI"),
    ("Jenkins", "jenkins/jenkins", "org.jenkins-ci.main:jenkins-war:Maven"),
    ("Keycloak", "keycloak/keycloak", "org.keycloak:keycloak-services:Maven"),
    ("Apache Guacamole", "guacamole/guacamole", "org.apache.guacamole:guacamole-client:Maven"),
    ("Graylog", "graylog/graylog", "org.graylog2:graylog2-server:Maven"),
    ("Strapi", "strapi/strapi", "strapi:npm"),
    ("Directus", "directus/directus", "directus:npm"),
    ("PrestaShop", "prestashop/prestashop", "prestashop/prestashop:Packagist"),
    ("OpenCart", "opencart/opencart", "opencart/opencart:Packagist"),
    ("BookStack", "bookstackapp/bookstack", "bookstackapp/bookstack:Packagist"),
    ("GLPI", "glpi/glpi", "glpi-project/glpi:Packagist"),
    ("Snipe-IT", "snipe/snipe-it", "snipe/snipe-it:Packagist"),
    ("Mautic", "mautic/mautic", "mautic/core:Packagist"),
]


def export_to_csv():
    """Export the project data to filtered_list.csv"""
    with open("filtered_list.csv", "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Project Name", "Docker Repository", "OSV Search Term"])
        for project, docker_repo, osv_term in PROJECT_REPOS:
            writer.writerow([project, docker_repo, osv_term])


def main(argv: List[str]) -> int:
    import argparse
    
    parser = argparse.ArgumentParser(description="Check existence of Docker Hub repositories for known web apps.")
    parser.add_argument("--timeout", type=int, default=20, help="HTTP timeout in seconds for each check.")
    parser.add_argument(
        "--tags",
        type=int,
        default=0,
        help="If > 0, also fetch and print up to N tags for repos that exist."
    )
    parser.add_argument("--export-csv", action="store_true", help="Export project data to filtered_list.csv")
    args = parser.parse_args(argv)

    total = len(PROJECT_REPOS)
    found = 0
    filtered_repos = []

    for project, repo, osv_term in PROJECT_REPOS:
        exists = False
        try:
            exists = repository_exists(repo, timeout=args.timeout)
        except Exception as e:
            print(f"[ERROR] {project:20s}  {repo:35s}  error={e}")
            continue

        if exists:
            found += 1
            filtered_repos.append((project, repo, osv_term))
            print(f"[FOUND] {project:20s}  {repo:35s}")
            if args.tags > 0:
                try:
                    tags = list_tags(repo, page_size=args.tags, timeout=args.timeout)
                    if tags:
                        joined = ", ".join(tags)
                        print(f"        tags: {joined}")
                    else:
                        print("        tags: <none>")
                except Exception as e:
                    print(f"        tags: <error: {e}>")
        else:
            print(f"[MISS ] {project:20s}  {repo:35s}")

    print(f"\nSummary: {found}/{total} repositories found.")
    
    # Export filtered results to CSV
    with open("filtered_list.csv", "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Project Name", "Docker Repository", "OSV Search Term"])
        for project, docker_repo, osv_term in filtered_repos:
            writer.writerow([project, docker_repo, osv_term])
    
    print(f"Exported {len(filtered_repos)} existing repositories to filtered_list.csv")
    return 0
if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
