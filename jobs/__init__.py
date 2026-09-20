"""Job engine registry and shared utilities."""

from datetime import datetime, timezone


def now_utc():
    """Return timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


# Severity weights for priority scoring
SEVERITY_WEIGHTS = {
    'Critical': 10,
    'High': 7,
    'Medium': 4,
    'Low': 1,
}

# Issue explanations
ISSUE_EXPLANATIONS = {
    '4xx Error': {
        'why': 'Broken URLs return errors to users and search engines, wasting crawl budget and damaging user experience.',
        'action': 'Investigate the broken URL. If the content exists elsewhere, set up a 301 redirect. If not, remove internal links pointing to it.',
    },
    '5xx Error': {
        'why': 'Server errors indicate backend problems that prevent search engines from crawling and indexing content.',
        'action': 'Check server logs for the error cause. Fix the backend issue or contact your hosting provider.',
    },
    'Redirect': {
        'why': 'Excessive redirects slow down page loading and waste crawl budget. Internal links should point to final URLs.',
        'action': 'Update internal links to point directly to the final destination URL instead of the redirecting URL.',
    },
    'Missing Title': {
        'why': 'Title tags are the most important on-page SEO element. Missing titles severely hurt rankings and CTR.',
        'action': 'Add a unique, descriptive title tag under 60 characters that includes target keywords.',
    },
    'Title Too Long': {
        'why': 'Titles over 60 characters get truncated in search results, reducing click-through rate.',
        'action': 'Shorten the title to under 60 characters while keeping the most important keywords at the front.',
    },
    'Missing Meta Description': {
        'why': 'Meta descriptions influence CTR. Without one, Google auto-generates snippets that may not be optimal.',
        'action': 'Write a compelling meta description (120-160 chars) that includes target keywords and a clear value proposition.',
    },
    'Missing Canonical': {
        'why': 'Without a canonical tag, search engines may index duplicate versions of the page, diluting ranking signals.',
        'action': 'Add a self-referencing canonical tag, or point it to the preferred version if duplicates exist.',
    },
    'Non-Indexable': {
        'why': 'Non-indexable pages are excluded from search results entirely, losing all potential organic traffic.',
        'action': 'If this page should be indexed, remove noindex directives. If intentional, verify it is correct.',
    },
    'Robots Blocked': {
        'why': 'Pages blocked by robots.txt cannot be crawled by search engines, preventing indexing entirely.',
        'action': 'If this page should be accessible, update robots.txt to allow crawling. Verify the block is intentional.',
    },
    'Zero Internal Links': {
        'why': 'Orphan pages with no internal links are hard for search engines to discover and rank poorly.',
        'action': 'Add contextual internal links from relevant pages to this URL to improve discoverability.',
    },
    'Not in Sitemap': {
        'why': 'Pages missing from the sitemap may be deprioritized or missed during crawling.',
        'action': 'Add this URL to the XML sitemap if it should be indexed.',
    },
    'Thin Content': {
        'why': 'Pages with very little content provide low value and are likely to rank poorly or be flagged as low quality.',
        'action': 'Expand the content with useful, original information. Aim for at least 300 words for product pages.',
    },
}
