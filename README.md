# BrieflyReport

A privacy-first browser tool that turns marketing CSV exports into a client-ready summary. This MVP is a single static HTML page and has no backend or paid API dependency.

## Current functionality
- CSV parsing in the browser; file data is not sent to a server.
- Summary cards for common marketing metrics (clicks, impressions, conversions, revenue, spend, CTR, CPC, CPA, ROAS).
- Simple chart, heuristic observations, standalone HTML export, and print-to-PDF workflow.
- Built-in sample data, mobile-responsive UI, basic file-size validation.
- Landing page metadata and FAQ.

## Run locally
Open `index.html` in a modern browser. No build step is required.

## Deploy
This is a static site. Deploy the repository as a static site on a host that permits commercial use. Cloudflare Pages' free tier documents unlimited static requests and bandwidth; its current limits should be checked before launch. GitHub Pages explicitly says it is not intended for running an online business or commercial SaaS, so do not use GitHub Pages as the production host for a paid service.

## Important: payments and revenue are not enabled
- The $3 price is a hypothesis, not a proven price.
- No checkout is integrated and no payment has been collected.
- Before charging users, choose a payment processor that supports the owner's country and payout method, complete identity/business verification, and implement verified server-side payment webhooks or use a merchant-of-record storefront.
- Confirm actual payout eligibility from Egypt before publishing a paid offer. Stripe's current supported-country list does not list Egypt. Gumroad charges 10% + $0.50 on direct sales (and 30% through Discover); its payout options vary by country. Verify payout access before relying on it.
- Do not simulate a successful payment in the UI. After payment integration, unlock paid deliverables only after verifying the provider's signed webhook/server-side status.

## Product and market risks
- Free alternatives (for example Looker Studio) are strong substitutes for full dashboards.
- This MVP's differentiation is fast file-based reporting without account setup, and privacy by local processing. It does not have direct Google/Meta connectors or AI-written analysis.
- Metric names and definitions differ between platforms. Always review results before sharing with a client.
- A live website does not guarantee traffic or sales. Validate demand before investing in custom domains, ads, or paid APIs.
