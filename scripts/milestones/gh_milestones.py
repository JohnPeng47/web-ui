#!/usr/bin/env python3
"""
GitHub Milestone and PR Explorer
A CLI tool to explore GitHub milestones, PRs, and commits

Usage:
    python gh_explorer.py list-milestones <owner>/<repo>
    python gh_explorer.py show-milestone <owner>/<repo> <milestone_id>
    python gh_explorer.py show-pr <owner>/<repo> <pr_number>

Example:
    python gh_explorer.py list-milestones joomla/joomla-cms
    python gh_explorer.py show-milestone joomla/joomla-cms 141
    python gh_explorer.py show-pr joomla/joomla-cms 45272
"""

import argparse
import requests
import json
import sys
from datetime import datetime
from typing import Dict, List, Optional
import os

class GitHubExplorer:
    def __init__(self, token: Optional[str] = None):
        self.base_url = "https://api.github.com"
        self.session = requests.Session()
        
        # Set up authentication if token is provided
        if token:
            self.session.headers.update({
                'Authorization': f'token {token}',
                'Accept': 'application/vnd.github.v3+json'
            })
        else:
            self.session.headers.update({
                'Accept': 'application/vnd.github.v3+json'
            })
    
    def _make_request(self, url: str, params: Dict = None) -> requests.Response:
        """Make a request to the GitHub API with error handling"""
        try:
            response = self.session.get(url, params=params)
            
            # Check rate limit
            if 'X-RateLimit-Remaining' in response.headers:
                remaining = int(response.headers['X-RateLimit-Remaining'])
                if remaining < 10:
                    print(f"⚠️  Warning: Only {remaining} API requests remaining")
            
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as e:
            if response.status_code == 403:
                print("❌ Rate limit exceeded or access denied. Consider using a GitHub token.")
                print("   Set GITHUB_TOKEN environment variable or use --token option")
            elif response.status_code == 404:
                print("❌ Repository or resource not found")
            else:
                print(f"❌ HTTP Error: {e}")
            sys.exit(1)
        except requests.exceptions.RequestException as e:
            print(f"❌ Request Error: {e}")
            sys.exit(1)
    
    def get_milestones(self, owner: str, repo: str) -> List[Dict]:
        """Get all milestones for a repository (both open and closed)"""
        milestones = []
        
        # Get open milestones
        url = f"{self.base_url}/repos/{owner}/{repo}/milestones"
        params = {'state': 'open', 'per_page': 100}
        
        while url:
            response = self._make_request(url, params)
            milestones.extend(response.json())
            
            # Check for pagination
            if 'next' in response.links:
                url = response.links['next']['url']
                params = None  # URL already contains params
            else:
                break
        
        # Get closed milestones
        url = f"{self.base_url}/repos/{owner}/{repo}/milestones"
        params = {'state': 'closed', 'per_page': 100}
        
        while url:
            response = self._make_request(url, params)
            milestones.extend(response.json())
            
            # Check for pagination
            if 'next' in response.links:
                url = response.links['next']['url']
                params = None
            else:
                break
        
        return milestones
    
    def get_milestone_issues(self, owner: str, repo: str, milestone_number: int) -> List[Dict]:
        """Get all issues/PRs for a specific milestone"""
        issues = []
        url = f"{self.base_url}/repos/{owner}/{repo}/issues"
        params = {
            'milestone': milestone_number,
            'state': 'all',  # Get both open and closed
            'per_page': 100
        }
        
        while url:
            response = self._make_request(url, params)
            issues.extend(response.json())
            
            if 'next' in response.links:
                url = response.links['next']['url']
                params = None
            else:
                break
        
        return issues
    
    def get_pr_details(self, owner: str, repo: str, pr_number: int) -> Dict:
        """Get detailed information about a specific PR"""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}"
        response = self._make_request(url)
        return response.json()
    
    def get_pr_commits(self, owner: str, repo: str, pr_number: int) -> List[Dict]:
        """Get commits for a specific PR"""
        url = f"{self.base_url}/repos/{owner}/{repo}/pulls/{pr_number}/commits"
        response = self._make_request(url)
        return response.json()
    
    def format_date(self, date_str: str) -> str:
        """Format ISO date string to readable format"""
        if not date_str:
            return "N/A"
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M UTC')
        except:
            return date_str
    
    def list_milestones(self, owner: str, repo: str):
        """List all milestones for a repository"""
        print(f"🎯 Fetching milestones for {owner}/{repo}...")
        milestones = self.get_milestones(owner, repo)
        
        if not milestones:
            print("No milestones found.")
            return
        
        # Sort by number (newest first)
        milestones.sort(key=lambda x: x['number'], reverse=True)
        
        print(f"\n📋 Found {len(milestones)} milestones:\n")
        print(f"{'ID':<4} {'State':<8} {'Title':<40} {'Progress':<12} {'Due Date':<20}")
        print("=" * 90)
        
        for milestone in milestones:
            progress = f"{milestone['closed_issues']}/{milestone['open_issues'] + milestone['closed_issues']}"
            due_date = self.format_date(milestone['due_on']) if milestone['due_on'] else "No due date"
            
            print(f"{milestone['number']:<4} {milestone['state']:<8} {milestone['title'][:38]:<40} {progress:<12} {due_date:<20}")
        
        print(f"\n💡 Use 'show-milestone {owner}/{repo} <ID>' to see PRs for a specific milestone")
    
    def show_milestone(self, owner: str, repo: str, milestone_id: int):
        """Show details of a specific milestone and its PRs"""
        print(f"🎯 Fetching milestone {milestone_id} for {owner}/{repo}...")
        
        # Get milestone details
        url = f"{self.base_url}/repos/{owner}/{repo}/milestones/{milestone_id}"
        try:
            response = self._make_request(url)
            milestone = response.json()
        except:
            print(f"❌ Milestone {milestone_id} not found")
            return
        
        # Get issues/PRs for this milestone
        issues = self.get_milestone_issues(owner, repo, milestone_id)
        
        # Filter PRs (issues with pull_request field)
        prs = [issue for issue in issues if 'pull_request' in issue]
        regular_issues = [issue for issue in issues if 'pull_request' not in issue]
        
        print(f"\n📌 Milestone: {milestone['title']}")
        print(f"📅 State: {milestone['state']}")
        print(f"📊 Progress: {milestone['closed_issues']}/{milestone['open_issues'] + milestone['closed_issues']} issues closed")
        if milestone['description']:
            print(f"📝 Description: {milestone['description']}")
        if milestone['due_on']:
            print(f"⏰ Due Date: {self.format_date(milestone['due_on'])}")
        
        print(f"\n🔀 Pull Requests ({len(prs)}):")
        print("=" * 100)
        
        if not prs:
            print("No pull requests found for this milestone.")
        else:
            print(f"{'ID':<4} {'#':<6} {'State':<8} {'Title':<45} {'Author':<15} {'Updated':<20}")
            print("-" * 100)
            
            for i, pr in enumerate(prs, 1):
                labels = [label['name'] for label in pr['labels']]
                state_emoji = "✅" if pr['state'] == 'closed' else "🔄"
                
                print(f"{i:<4} #{pr['number']:<5} {state_emoji} {pr['state']:<6} {pr['title'][:43]:<45} {pr['user']['login']:<15} {self.format_date(pr['updated_at']):<20}")
                
                if labels:
                    print(f"     🏷️  Labels: {', '.join(labels[:5])}")  # Show first 5 labels
                print()
        
        if regular_issues:
            print(f"\n📋 Issues ({len(regular_issues)}):")
            print("=" * 100)
            print(f"{'ID':<4} {'#':<6} {'State':<8} {'Title':<45} {'Author':<15} {'Updated':<20}")
            print("-" * 100)
            
            for i, issue in enumerate(regular_issues, len(prs) + 1):
                labels = [label['name'] for label in issue['labels']]
                state_emoji = "✅" if issue['state'] == 'closed' else "🔄"
                
                print(f"{i:<4} #{issue['number']:<5} {state_emoji} {issue['state']:<6} {issue['title'][:43]:<45} {issue['user']['login']:<15} {self.format_date(issue['updated_at']):<20}")
                
                if labels:
                    print(f"     🏷️  Labels: {', '.join(labels[:5])}")
                print()
        
        print(f"\n💡 Use 'show-pr {owner}/{repo} <PR_NUMBER>' to see details and commits for a specific PR")
    
    def show_pr(self, owner: str, repo: str, pr_number: int):
        """Show detailed information about a specific PR including commits"""
        print(f"🔀 Fetching PR #{pr_number} for {owner}/{repo}...")
        
        try:
            pr = self.get_pr_details(owner, repo, pr_number)
            commits = self.get_pr_commits(owner, repo, pr_number)
        except:
            print(f"❌ PR #{pr_number} not found")
            return
        
        # Display PR information
        print(f"\n📋 Pull Request #{pr['number']}: {pr['title']}")
        print("=" * 80)
        print(f"👤 Author: {pr['user']['login']}")
        print(f"📅 Created: {self.format_date(pr['created_at'])}")
        print(f"📅 Updated: {self.format_date(pr['updated_at'])}")
        if pr['closed_at']:
            print(f"📅 Closed: {self.format_date(pr['closed_at'])}")
        if pr['merged_at']:
            print(f"📅 Merged: {self.format_date(pr['merged_at'])}")
        
        print(f"🎯 State: {pr['state']} {'(merged)' if pr['merged'] else ''}")
        print(f"🌿 Base: {pr['base']['ref']} ← Head: {pr['head']['ref']}")
        
        # Labels
        if pr['labels']:
            labels = [label['name'] for label in pr['labels']]
            print(f"🏷️  Labels: {', '.join(labels)}")
        
        # Milestone
        if pr['milestone']:
            print(f"🎯 Milestone: {pr['milestone']['title']}")
        
        # Stats
        print(f"📊 Changes: +{pr['additions']} -{pr['deletions']} ({pr['changed_files']} files)")
        print(f"💬 Comments: {pr['comments']} | Reviews: {pr['review_comments']}")
        
        # Description
        if pr['body']:
            print(f"\n📝 Description:")
            print("-" * 40)
            # Truncate long descriptions
            description = pr['body']
            if len(description) > 500:
                description = description[:500] + "... (truncated)"
            print(description)
        
        # Commits
        print(f"\n🔄 Commits ({len(commits)}):")
        print("=" * 80)
        
        if not commits:
            print("No commits found.")
        else:
            for i, commit in enumerate(commits, 1):
                sha_short = commit['sha'][:8]
                message = commit['commit']['message'].split('\n')[0]  # First line only
                author = commit['commit']['author']['name']
                date = self.format_date(commit['commit']['author']['date'])
                
                print(f"{i:2}. {sha_short} - {message[:60]}")
                print(f"    👤 {author} on {date}")
                print(f"    🔗 {commit['html_url']}")
                print()
        
        # URLs
        print(f"🔗 PR URL: {pr['html_url']}")
        if pr['merged']:
            print(f"🔗 Diff URL: {pr['html_url']}/files")

def main():
    parser = argparse.ArgumentParser(
        description="GitHub Milestone and PR Explorer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s list-milestones joomla/joomla-cms
  %(prog)s show-milestone joomla/joomla-cms 141
  %(prog)s show-pr joomla/joomla-cms 45272

Environment Variables:
  GITHUB_TOKEN - GitHub personal access token for higher rate limits
        """
    )
    
    parser.add_argument('--token', help='GitHub personal access token')
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List milestones command
    list_parser = subparsers.add_parser('list-milestones', help='List all milestones for a repository')
    list_parser.add_argument('repo', help='Repository in format owner/repo')
    
    # Show milestone command
    milestone_parser = subparsers.add_parser('show-milestone', help='Show details of a specific milestone')
    milestone_parser.add_argument('repo', help='Repository in format owner/repo')
    milestone_parser.add_argument('milestone_id', type=int, help='Milestone ID number')
    
    # Show PR command
    pr_parser = subparsers.add_parser('show-pr', help='Show details of a specific PR')
    pr_parser.add_argument('repo', help='Repository in format owner/repo')
    pr_parser.add_argument('pr_number', type=int, help='Pull Request number')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Get GitHub token from argument or environment
    token = args.token or os.getenv('GITHUB_TOKEN')
    
    if not token:
        print("⚠️  No GitHub token provided. API rate limits will be lower.")
        print("   Set GITHUB_TOKEN environment variable or use --token option for better performance.")
        print()
    
    # Parse repository
    try:
        owner, repo = args.repo.split('/', 1)
    except ValueError:
        print("❌ Invalid repository format. Use: owner/repo")
        sys.exit(1)
    
    # Initialize explorer
    explorer = GitHubExplorer(token)
    
    # Execute command
    try:
        if args.command == 'list-milestones':
            explorer.list_milestones(owner, repo)
        elif args.command == 'show-milestone':
            explorer.show_milestone(owner, repo, args.milestone_id)
        elif args.command == 'show-pr':
            explorer.show_pr(owner, repo, args.pr_number)
    except KeyboardInterrupt:
        print("\n👋 Interrupted by user")
        sys.exit(0)

if __name__ == '__main__':
    main()