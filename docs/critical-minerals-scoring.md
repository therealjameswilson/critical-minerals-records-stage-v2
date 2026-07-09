# Critical Minerals Scoring

`scorer.py` gives each event an integer score used for sorting and thresholding.
The score is a transparent editorial aid, not a factual claim.

Records score higher when they have:

- Official U.S. government source type or `.gov` / `.mil` citation URLs.
- Strong evidence type: historical record, archival record, trade data, policy document, statistical release, or ministerial document.
- Direct critical-minerals language in title, description, subjects, minerals, or supply-chain stage.
- Named minerals, countries, agencies, supply-chain stages, FSO use cases, or HS codes.
- Historical/archival context or current policy/statistical/trade relevance.
- High confidence, useful descriptions, stable HTTPS citation URLs, and explicit caveats.

Low-confidence records are not hidden automatically; they receive a lower score and appear with a visible "Needs Review" badge in Records Stage.

The intent is simple:

1. Put official, well-described, sourceable records near the top.
2. Keep placeholder and proxy records visible but clearly caveated.
3. Make scoring easy to audit before a briefing or clearance review.
