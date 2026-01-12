# YouTube Transcript → Vietnamese Summary → Email Workflow

## Objective
Extract YouTube video transcript, generate Vietnamese summary, and send via Gmail.

---

## Required Inputs
1. **YouTube URL** - Full video URL (e.g., `https://www.youtube.com/watch?v=...`)
2. **Recipient Email** - Where to send the summary (default: `giabaongb0305@gmail.com`)
3. **Language** - Summary language (default: Vietnamese)

---

## Tools/Scripts Used
1. **`execution/summarize_youtube.py`** - Scrapes transcript via Apify + summarizes with Azure OpenAI
2. **`execution/send_email.py`** - Sends email via Gmail API

---

## Workflow Steps

### Step 1: Extract Transcript
**Tool:** Apify `scrape-creators/best-youtube-transcripts-scraper`

**Process:**
1. Call Apify actor with YouTube URL
2. Wait for transcript extraction (30-60 seconds)
3. Retrieve transcript text from dataset

**Validation:**
- ✅ Transcript is not empty
- ✅ Transcript length > 100 characters (avoid failures)

**Error Handling:**
- Video has no captions → Notify user
- Private video → Notify user
- Invalid URL → Validate before API call

---

### Step 2: Summarize in Vietnamese
**Tool:** Azure OpenAI GPT-4o

**Prompt Template:**
```
Hãy tóm tắt nội dung video YouTube này bằng tiếng Việt.

Cấu trúc:
1. **Chủ đề**: Video nói về gì (1 dòng)
2. **Điểm chính**: Các ý chính cần ghi nhớ (dạng bullet points)
3. **Tóm tắt chi tiết**: 2-3 đoạn văn mô tả nội dung

Transcript:
{transcript}
```

**Quality Thresholds:**
- Summary length: 300-1000 words
- Must be in Vietnamese (validate with simple check)
- Must include all 3 sections (Title, Key Points, Summary)

---

### Step 3: Send Email via Gmail
**Tool:** Gmail API (OAuth2)

**Email Format:**
- **To:** User's Gmail (from `.env` or parameter)
- **Subject:** `📺 Tóm tắt Video YouTube - {video_title}`
- **Body:** Vietnamese summary (formatted as plain text or HTML)

**Validation:**
- ✅ OAuth token is valid (refresh if expired)
- ✅ Email sent successfully (check Gmail API response)

---

## Expected Outputs

### Success Case
```
✓ Transcript extracted: 5,243 words
✓ Summary generated: 642 words (Vietnamese)
✓ Email sent to: giabaongb0305@gmail.com
→ Subject: 📺 Tóm tắt Video YouTube - "How to Build Reliable AI Systems"
```

### Output Format (Email Body)
```
📺 TÓM TẮT VIDEO YOUTUBE

Video: {title}
Link: {url}
Độ dài: {duration}

---

**Chủ đề**: {one-line topic}

**Điểm chính**:
• {key point 1}
• {key point 2}
• {key point 3}

**Tóm tắt chi tiết**:
{2-3 paragraph summary in Vietnamese}

---

🤖 Được tạo tự động bởi Anti-Gravity DO Framework
```

---

## Edge Cases & Constraints

### Edge Case 1: Video Too Long (>2 hours)
**Problem:** Transcript exceeds token limits (15,000 chars)
**Solution:** Truncate transcript to first 15,000 chars + add note in summary

### Edge Case 2: Non-English Video
**Problem:** Transcript in foreign language
**Solution:** LLM auto-translates to Vietnamese during summarization

### Edge Case 3: Gmail OAuth Token Expired
**Problem:** Gmail API returns 401 Unauthorized
**Solution:** Auto-refresh token (handled by `send_email.py`)

### Edge Case 4: No Transcript Available
**Problem:** Video doesn't have captions
**Solution:** Notify user + skip summarization

---

## Quality Thresholds

| Metric | Target | Action if Below |
|--------|--------|----------------|
| Transcript length | >100 chars | Abort (invalid video) |
| Summary length | 300-1000 words | Regenerate with better prompt |
| Email delivery rate | 100% | Retry up to 3 times |
| Vietnamese language | 100% | Add explicit language instruction |

---

## API Rate Limits

### Apify
- **Limit:** 100 requests/month (free tier)
- **Cost:** $0.25 per 1,000 requests (paid tier)
- **Mitigation:** No rate limiting needed (single request)

### Azure OpenAI
- **Limit:** 10 requests/minute
- **Cost:** ~$0.01 per summary (GPT-4o)
- **Mitigation:** No rate limiting needed (single request)

### Gmail API
- **Limit:** 100 emails/day (OAuth user)
- **Mitigation:** No rate limiting needed (single request)

---

## Cost Estimate (per run)
- Apify transcript scrape: ~$0.001
- Azure OpenAI summarization: ~$0.01
- Gmail API: Free
- **Total: ~$0.011 per video**

---

## Dependencies
- `apify-client` (Python package)
- `openai` (Azure SDK)
- `google-auth`, `google-auth-oauthlib`, `google-api-python-client`
- `.env` file with:
  - `APIFY_API_KEY`
  - `AZURE_OPENAI_API_KEY`
  - `AZURE_OPENAI_ENDPOINT`
  - `AZURE_OPENAI_DEPLOYMENT`
- `credentials.json` (Google OAuth)
- `token.json` (Gmail authentication)

---

## Usage Example

### CLI Usage (separate steps)
```bash
# Step 1: Extract + Summarize
python3 execution/summarize_youtube.py --url "https://www.youtube.com/watch?v=dQw4w9WgXcQ" --lang vi

# Step 2: Send Email
python3 execution/send_email.py \
  --to "giabaongb0305@gmail.com" \
  --subject "📺 Tóm tắt Video YouTube" \
  --body "$(cat summary.txt)" \
  --mode send
```

### Unified Workflow (orchestrated by Claude)
```
User: "Summarize this YouTube video in Vietnamese and email it to me: https://www.youtube.com/watch?v=..."

Agent:
1. Call summarize_youtube.py with --lang vi
2. Capture summary output
3. Call send_email.py with summary as body
4. Return: "✓ Email sent!"
```

---

## Self-Annealing Notes

### Version 1.0 (Jan 1, 2026)
- Initial workflow created
- Uses existing tools: `summarize_youtube.py` + `send_email.py`
- Vietnamese support requires prompt update (not yet implemented)
- Email sending works but needs error handling improvements

### Known Improvements Needed
1. [ ] Update `summarize_youtube.py` to accept `--lang` parameter
2. [ ] Add Vietnamese prompt template
3. [ ] Add video title extraction for email subject
4. [ ] Create unified wrapper script for one-command execution
5. [ ] Add HTML formatting for email body (nicer presentation)
6. [ ] Add attachment option (export summary as PDF/DOCX)

---

## Testing Checklist

Before marking complete, verify:
- [ ] Transcript extraction works for public YouTube video
- [ ] Summary is in Vietnamese (not English)
- [ ] Email sent successfully to Gmail
- [ ] Email subject includes video title
- [ ] Email body is well-formatted
- [ ] Error handling works (invalid URL, private video, etc.)

---

**Status:** ✅ Directive complete. Ready for implementation.