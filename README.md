# حِسبة | Hesba

An Arabic-first toolkit for freelancers and small businesses: pricing calculators, profit-margin analysis, break-even analysis, invoice/quotation generation, free templates, practical guides, and an optional paid digital kit.

## Public services

- **Website:** https://hesba-income-tools.onrender.com/
- **Resources:** https://hesba-income-tools.onrender.com/resources.html
- **Free sample templates:** https://hesba-income-tools.onrender.com/free-samples.html
- **Business tracker guide:** https://hesba-income-tools.onrender.com/business-tracker-guide.html
- **Payments API:** https://hesba-payments-api.onrender.com/
- **API health:** https://hesba-payments-api.onrender.com/health
- **Public checkout configuration:** https://hesba-payments-api.onrender.com/api/config

## What the product includes

- Hourly-rate calculator using target income, working costs, billable hours and reserve.
- Profit-margin calculator distinguishing margin from markup.
- Break-even calculator for fixed costs, contribution per unit and target profit.
- Arabic invoice/quotation builder with print/PDF, local drafts and JSON backup.
- Free Arabic guides and downloadable templates.
- Paid **Hesba Freelancer Desk Kit (Arabic), v1.2**: 12 templates, an Excel business tracker workbook with 6 sheets (including a lead pipeline, calculated invoice status, dropdown validations and conditional formatting), and 3 CSV trackers. The workbook is designed for one currency per file. Current displayed price: **$5.99 USD**.

## Accurate current launch state

The site is deployed and the public calculator UI has passed live functional checks. The product bundle integrity check currently reports `product_pack_valid=true` and `product_pack_issue=valid`.

**Online checkout is deliberately disabled.** The live payment API reports `checkout_configured=false`, `checkout_enabled=false`, and `paypal_mode=sandbox`. No live merchant credentials have been configured, and no sales or revenue have been recorded. Do not treat site availability or accepted IndexNow notifications as evidence of revenue, organic traffic, or search ranking.

The buyer download-recovery route `POST /api/orders/reissue-download` re-checks the order at PayPal, validates the product signature, price/currency, completed capture, and payer email before issuing a short-lived download token. It remains fail-closed while checkout is disabled. Tokens are sent in an Authorization header, not placed in URLs.

## Privacy and data handling

The public calculators work locally in the browser. Invoice content and local drafts are not uploaded to a Hesba database. If checkout is activated in the future, PayPal processes the payment details; the site does not ask users to enter card details into Hesba.

See [privacy.html](https://hesba-income-tools.onrender.com/privacy.html) and [terms.html](https://hesba-income-tools.onrender.com/terms.html).

## Repository structure

- `hesba/`: static public website, assets, guides, downloads, sitemap/RSS, and machine-readable resource listing.
- `hesba_payments.py`: FastAPI payment verification and protected download service.
- `tests/test_hesba_payments.py`: payment, checkout-lock and secure-download regression tests.
- `.github/workflows/hesba-payments-tests.yml`: GitHub Actions workflow for the payment tests.
- `hesba/OPERATIONS_AR.md`: current operations state, launch checklist and known gaps.

## Test status

Live browser checks verified the calculator tools, free-template page and downloadable templates. The payment API returns HTTP 200 on `/health` and `/api/config`, the product pack is valid, and a safe negative-path request with a missing recovery payload was rejected at request validation (HTTP 422). Checkout remains disabled.

Automated regression tests have been added but **have not been confirmed as passing**. Previous GitHub Actions attempts could not start because GitHub reported an account billing lock. Do not claim the unit test suite is green until an actual test run completes successfully.

## Safe launch checklist

- [ ] Configure verified live PayPal merchant credentials in Render environment variables, never in Git.
- [ ] Confirm `/api/config` only enables checkout in live mode and does not expose secrets.
- [ ] Run regression tests successfully and exercise the checkout flow in PayPal sandbox.
- [ ] Verify successful payment, wrong email, incorrect amount/currency, unpaid order, expired token and successful ZIP delivery.
- [ ] Review refund/support disclosures and jurisdiction-specific legal obligations before enabling live sales.
- [ ] Test on multiple browsers and devices; monitor delivery failures and buyer support.
- [ ] Keep product decryption/signing secrets backed up securely outside the repository.

## No guaranteed income claim

Hesba is a launched product with an unactivated payment rail. Revenue requires live payment setup, visitors, conversion and customer demand. Daily income is not guaranteed.