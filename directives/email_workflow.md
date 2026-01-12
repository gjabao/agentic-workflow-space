# Email Workflow Directive

## Goal
Enable automated drafting and sending of emails using Gmail API.

## SOP
1.  **Safety First**: ALWAYS default to `draft` mode unless `send` is explicitly requested.
2.  **Rate Limits**: Gmail sends are limited (approx 2000/day for paid, 500/day for free). Do not exceed.
3.  **Authentication**: Requires `https://www.googleapis.com/auth/gmail.compose` (for drafts/sending) or `gmail.modify`.

## Usage
```bash
# Draft Mode (Recommended)
python3 execution/send_email.py --to "lead@example.com" --subject "Hello" --body "Hi there" --mode draft

# Send Mode
python3 execution/send_email.py --to "lead@example.com" --subject "Hello" --body "Hi there" --mode send
```

## Inputs
- `credentials.json`: OAuth Client ID.
- `token.json`: User Access Token (Must have Gmail scopes).
