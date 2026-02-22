"""GitHub scraper using PyGithub"""

from scrapers.base_scraper import BaseScraper
from typing import AsyncGenerator, Optional, Dict
from utils.logger import log
from utils.validators import extract_emails_from_text, is_valid_email
from github import Github, GithubException
import asyncio
import re


class GitHubScraper(BaseScraper):
    """Scraper for GitHub using PyGithub"""

    def __init__(self, *args, **kwargs):
        super().__init__("github", *args, **kwargs)

        self.search_queries = [
            "SaaS marketing automation",
            "B2B content platform",
            "LinkedIn automation",
            "AI content generation",
            "growth marketing tool",
            "B2B SaaS product"
        ]

        self.github_client = None

    async def _initialize_github(self):
        """Initialize GitHub client"""
        # Get API key
        api_key = await self.api_key_rotator.get_key('github')

        if not api_key:
            log.warning("No GitHub API keys available, using unauthenticated access")
            return Github()

        try:
            github = Github(api_key.key)
            # Test authentication
            github.get_user().login
            return github

        except GithubException as e:
            log.error(f"GitHub authentication failed: {e}")
            await self.api_key_rotator.mark_invalid(api_key)
            return Github()  # Fall back to unauthenticated

    async def scrape(self) -> AsyncGenerator[dict, None]:
        """Scrape GitHub for leads"""

        # Initialize GitHub client
        self.github_client = await self._initialize_github()

        # Search for repositories
        for query in self.search_queries:
            log.info(f"{self.source_name}: Searching for '{query}'")

            try:
                # Run GitHub search in thread pool (PyGithub is synchronous)
                repos = await asyncio.to_thread(
                    self._search_repositories,
                    query
                )

                for repo_data in repos:
                    yield repo_data

            except Exception as e:
                log.error(f"Error searching GitHub for '{query}': {e}")
                continue

    def _search_repositories(self, query: str, max_results: int = 50) -> list:
        """Search repositories (runs in thread pool)"""
        results = []

        try:
            repos = self.github_client.search_repositories(
                query=query,
                sort='stars',
                order='desc'
            )

            for i, repo in enumerate(repos):
                if i >= max_results:
                    break

                try:
                    # Get repo data
                    repo_data = {
                        'name': repo.name,
                        'full_name': repo.full_name,
                        'description': repo.description or '',
                        'stars': repo.stargazers_count,
                        'url': repo.html_url,
                        'owner': repo.owner.login if repo.owner else None,
                        'owner_type': repo.owner.type if repo.owner else None,
                        'created_at': repo.created_at.isoformat() if repo.created_at else None,
                        'language': repo.language,
                        'topics': repo.get_topics() if hasattr(repo, 'get_topics') else []
                    }

                    # Get README for additional info
                    try:
                        readme = repo.get_readme()
                        content = readme.decoded_content.decode('utf-8', errors='ignore')
                        repo_data['readme'] = content[:5000]  # Limit size
                    except:
                        repo_data['readme'] = ''

                    # Get owner data
                    if repo.owner:
                        try:
                            owner = repo.owner
                            repo_data['owner_data'] = {
                                'login': owner.login,
                                'name': owner.name,
                                'email': owner.email,
                                'company': owner.company,
                                'location': owner.location,
                                'bio': owner.bio,
                                'blog': owner.blog,
                                'twitter': owner.twitter_username,
                                'public_repos': owner.public_repos
                            }
                        except:
                            repo_data['owner_data'] = {}

                    # Get contributors
                    try:
                        contributors = []
                        for contributor in repo.get_contributors()[:5]:  # Top 5
                            contributors.append({
                                'login': contributor.login,
                                'name': contributor.name,
                                'email': contributor.email,
                                'contributions': contributor.contributions
                            })
                        repo_data['contributors'] = contributors
                    except:
                        repo_data['contributors'] = []

                    results.append(repo_data)

                except Exception as e:
                    log.debug(f"Error processing repo: {e}")
                    continue

        except GithubException as e:
            if e.status == 403:
                log.warning("GitHub rate limit reached")
            else:
                log.error(f"GitHub search error: {e}")

        return results

    async def extract_lead_data(self, raw_data: dict) -> Optional[dict]:
        """Extract lead data from GitHub repository data"""

        # Try to extract from owner data first
        owner_data = raw_data.get('owner_data', {})

        email = owner_data.get('email')
        if email and is_valid_email(email):
            return self._create_lead_from_owner(raw_data, owner_data, email)

        # Try contributors
        for contributor in raw_data.get('contributors', []):
            email = contributor.get('email')
            if email and is_valid_email(email):
                return self._create_lead_from_contributor(raw_data, contributor, email)

        # Extract emails from README
        readme = raw_data.get('readme', '')
        if readme:
            emails = extract_emails_from_text(readme)
            if emails:
                return self._create_lead_from_readme(raw_data, emails[0], readme)

        return None

    def _create_lead_from_owner(self, repo_data: dict, owner_data: dict, email: str) -> dict:
        """Create lead from repository owner"""

        # Determine signal type
        signal_type = 'github_owner'
        readme = repo_data.get('readme', '').lower()
        if 'hiring' in readme:
            signal_type = 'hiring'

        # Build website URL
        website = owner_data.get('blog') or repo_data.get('url')

        # Build LinkedIn URL from name
        linkedin_url = None
        if owner_data.get('twitter'):
            # Could search LinkedIn by name later
            pass

        return {
            'email': email,
            'name': owner_data.get('name') or owner_data.get('login', 'Unknown'),
            'company': owner_data.get('company') or repo_data.get('name', 'Unknown'),
            'role': 'Repository Owner',
            'linkedin_url': linkedin_url,
            'website': website,
            'location': owner_data.get('location', ''),
            'signal_type': signal_type,
            'raw_data': str(repo_data)[:1000]
        }

    def _create_lead_from_contributor(self, repo_data: dict, contributor: dict, email: str) -> dict:
        """Create lead from contributor"""

        return {
            'email': email,
            'name': contributor.get('name') or contributor.get('login', 'Unknown'),
            'company': repo_data.get('name', 'Unknown'),
            'role': f'Contributor ({contributor.get("contributions", 0)} commits)',
            'linkedin_url': None,
            'website': repo_data.get('url'),
            'location': '',
            'signal_type': 'github_contributor',
            'raw_data': str(repo_data)[:1000]
        }

    def _create_lead_from_readme(self, repo_data: dict, email: str, readme: str) -> dict:
        """Create lead from README"""

        # Try to extract name and role from README
        name = self._extract_name_from_readme(readme)
        role = self._extract_role_from_readme(readme)
        company = repo_data.get('name', 'Unknown')

        # Check for hiring signals
        signal_type = 'github_readme'
        if any(kw in readme.lower() for kw in ['hiring', "we're hiring", 'join us']):
            signal_type = 'hiring'

        return {
            'email': email,
            'name': name,
            'company': company,
            'role': role,
            'linkedin_url': None,
            'website': repo_data.get('url'),
            'location': '',
            'signal_type': signal_type,
            'raw_data': str(repo_data)[:1000]
        }

    def _extract_name_from_readme(self, readme: str) -> str:
        """Extract name from README"""
        patterns = [
            r'(?:by|author|created by|maintained by)\s*[:\-]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
            r'## (?:Author|Creator|Maintainer)\s*\n\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})'
        ]

        for pattern in patterns:
            match = re.search(pattern, readme, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return "Unknown"

    def _extract_role_from_readme(self, readme: str) -> str:
        """Extract role from README"""
        patterns = [
            r'\b(founder|co-founder|CEO|CTO|creator|maintainer|author)\b'
        ]

        for pattern in patterns:
            match = re.search(pattern, readme, re.IGNORECASE)
            if match:
                return match.group(1).capitalize()

        return "Developer"
