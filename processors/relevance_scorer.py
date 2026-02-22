"""ICP matching and lead relevance scoring"""

from typing import Dict, Tuple
from config.icp_config import (
    TARGET_KEYWORDS,
    TITLE_KEYWORDS,
    COMPANY_TYPE_KEYWORDS,
    HIRING_KEYWORDS,
    FUNDING_KEYWORDS,
    ENGAGEMENT_KEYWORDS,
    SCORING_WEIGHTS,
    get_company_size_score,
    calculate_keyword_score
)
from utils.logger import log
import re


class RelevanceScorer:
    """Scores leads based on ICP matching"""

    def __init__(self):
        self.scoring_stats = {
            'total_scored': 0,
            'high_quality': 0,  # Score >= 7
            'medium_quality': 0,  # Score 5-6
            'low_quality': 0  # Score < 5
        }

    def score_lead(self, lead: Dict, raw_data: str = '') -> Tuple[int, Dict]:
        """
        Score a lead based on ICP criteria

        Args:
            lead: Lead dictionary
            raw_data: Raw data string for content analysis

        Returns:
            Tuple of (score, breakdown)
        """
        self.scoring_stats['total_scored'] += 1

        # Combine all text for analysis
        text_parts = [
            lead.get('name', ''),
            lead.get('company', ''),
            lead.get('role', ''),
            lead.get('signal_type', ''),
            raw_data
        ]
        combined_text = ' '.join(text_parts)

        # Calculate component scores
        icp_score = self._calculate_icp_match(lead, combined_text)
        hiring_score = self._calculate_hiring_signals(combined_text)
        funding_score = self._calculate_funding_signals(combined_text)
        engagement_score = self._calculate_engagement(combined_text)
        content_score = self._calculate_content_relevance(combined_text)

        # Apply weights
        weighted_icp = (icp_score / 10) * SCORING_WEIGHTS['icp_match']
        weighted_hiring = (hiring_score / 10) * SCORING_WEIGHTS['hiring_signals']
        weighted_funding = (funding_score / 10) * SCORING_WEIGHTS['funding_signals']
        weighted_engagement = (engagement_score / 10) * SCORING_WEIGHTS['engagement']
        weighted_content = (content_score / 10) * SCORING_WEIGHTS['content_relevance']

        # Total score (0-100 scale, converted to 0-10)
        total_weighted = (
            weighted_icp +
            weighted_hiring +
            weighted_funding +
            weighted_engagement +
            weighted_content
        )

        # Convert to 1-10 scale
        final_score = max(1, min(10, int(total_weighted / 10)))

        # Create breakdown
        breakdown = {
            'icp_match': round(icp_score, 1),
            'hiring_signals': round(hiring_score, 1),
            'funding_signals': round(funding_score, 1),
            'engagement': round(engagement_score, 1),
            'content_relevance': round(content_score, 1),
            'final_score': final_score
        }

        # Update stats
        if final_score >= 7:
            self.scoring_stats['high_quality'] += 1
        elif final_score >= 5:
            self.scoring_stats['medium_quality'] += 1
        else:
            self.scoring_stats['low_quality'] += 1

        return final_score, breakdown

    def _calculate_icp_match(self, lead: Dict, text: str) -> float:
        """Calculate ICP match score (0-10)"""
        score = 0.0

        # Title match (max 4 points)
        role = lead.get('role', '').lower()
        title_score = calculate_keyword_score(role, TITLE_KEYWORDS)
        score += min(4, title_score)

        # Company type (max 2 points)
        company = lead.get('company', '').lower()
        company_score = calculate_keyword_score(company + ' ' + text, COMPANY_TYPE_KEYWORDS)
        score += min(2, company_score)

        # Company size (max 2 points) - extract from text if available
        size_score = self._extract_company_size_score(text)
        score += size_score

        # LinkedIn presence (max 1 point)
        if lead.get('linkedin_url'):
            score += 1

        # Website presence (max 1 point)
        if lead.get('website'):
            score += 1

        return min(10, score)

    def _calculate_hiring_signals(self, text: str) -> float:
        """Calculate hiring signals score (0-10)"""
        score = calculate_keyword_score(text, HIRING_KEYWORDS)
        return min(10, score)

    def _calculate_funding_signals(self, text: str) -> float:
        """Calculate funding signals score (0-10)"""
        score = calculate_keyword_score(text, FUNDING_KEYWORDS)

        # Extract funding amount for bonus points
        funding_amount = self._extract_funding_amount(text)
        if funding_amount:
            # Bonus points for funding in target range ($500K - $10M)
            if 0.5 <= funding_amount <= 10:
                score += 2

        return min(10, score)

    def _calculate_engagement(self, text: str) -> float:
        """Calculate engagement score (0-10)"""
        score = calculate_keyword_score(text, ENGAGEMENT_KEYWORDS)
        return min(10, score)

    def _calculate_content_relevance(self, text: str) -> float:
        """Calculate content relevance score based on target keywords (0-10)"""
        text_lower = text.lower()
        matches = 0

        for keyword in TARGET_KEYWORDS:
            if keyword.lower() in text_lower:
                matches += 1

        # Each keyword match = 1 point, max 10
        return min(10, matches)

    def _extract_company_size_score(self, text: str) -> float:
        """Extract company size and return score"""
        # Look for employee count patterns
        patterns = [
            r'(\d+)\s*(?:to|-)\s*(\d+)\s*employees',
            r'team of (\d+)',
            r'(\d+)\s*people',
            r'(\d+)\s*member team'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    if len(match.groups()) == 2:
                        # Range
                        avg_size = (int(match.group(1)) + int(match.group(2))) / 2
                    else:
                        avg_size = int(match.group(1))

                    return get_company_size_score(int(avg_size))
                except ValueError:
                    continue

        return 0

    def _extract_funding_amount(self, text: str) -> float:
        """Extract funding amount in millions"""
        patterns = [
            r'\$(\d+(?:\.\d+)?)\s*(?:million|M)\b',
            r'\$(\d+(?:\.\d+)?)\s*(?:billion|B)\b'
        ]

        for i, pattern in enumerate(patterns):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                amount = float(match.group(1))
                if i == 1:  # Billion
                    amount *= 1000
                return amount

        return 0

    def get_stats(self) -> Dict:
        """Get scoring statistics"""
        return self.scoring_stats.copy()
