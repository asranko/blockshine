# THE DEPTHS | القاع

An Arabic-first social network concept focused on thoughtful discussion, meaningful interaction, a public constitution, and explainable moderation.

## What this prototype includes
- Responsive RTL Arabic interface and five views: Mirror/feed, Council of Nine, Constitution, Review Chamber, and Saved.
- Local demo feed with seed discussions, composer, intention tags (أفيد، أتعلم، أوثّق ذكرى، أطلب مساعدة), comments, votes, saves, and private meaningful signals (استفدت، فكرت، تواصلت معك).
- Twelve-hour "fridge" concept represented as a pending draft, with manual confirmation in the Review Chamber.
- Local demo reporting, an illustrative nine-role council, and an event log.
- Browser-local persistence using localStorage.

## Important limitations
This is a **front-end prototype**, not a production social network. It does not yet have real user accounts, server-side database, cross-device sync, actual AI moderation agents, real 12-hour background notifications, email delivery, abuse/rate-limit controls, human moderator operations, or verified appeals. The Council of Nine screen describes proposed roles; it does not call nine independent models. Reports, decisions, posts, and demo interactions remain in the visitor's browser and are not shared with other users.

Do not use this prototype for sensitive personal information or rely on it for real moderation or safety decisions.

## Next engineering milestones
1. Backend API and persistent PostgreSQL data model for users, posts, comments, reactions, reports, appeals, and audit events.
2. Authentication, account recovery, authorization, rate limiting, and server-side validation.
3. Real publication queue with scheduled 12-hour confirmation reminders and deletion/expiry policies.
4. Moderation pipeline: fast rules/classifier, escalation criteria, Council-of-Nine orchestration, transparent reason codes, dissent capture, and appeal workflow.
5. Security, privacy, accessibility, load, and end-to-end tests before public beta.

## Local run
Open `index.html` in a modern browser. No build step is required.
