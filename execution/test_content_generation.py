#!/usr/bin/env python3
"""
Test content generation to debug Instantly campaign issue
"""
import os
import json
from dotenv import load_dotenv
from openai import AzureOpenAI

load_dotenv()

# Initialize Azure OpenAI
client = AzureOpenAI(
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    api_version="2024-02-15-preview"
)

client_info = {
    "name": "Beauty Connect Shop",
    "description": "Canadian distributor of Dermaceutical Korean skincare products serving cosmetic clinics in Edmonton and across Canada. Launching Skools training platform for Korean treatment protocols.",
    "target_audience": "Cosmetic clinic owners, medical aestheticians, spa directors in Edmonton"
}

offer = "Edmonton Local Korean Skincare Access"

prompt = f"""
You are an expert cold email copywriter trained in SSM SOP, Connector Angle, and Anti-Fragile Method.

CONTEXT:
- Client: {client_info['name']}
- Description: {client_info['description']}
- Offer: {offer}
- Target Audience: {client_info['target_audience']}

TASK: Write cold email sequences following these frameworks.

REQUIRED OUTPUT FORMAT (JSON):
{{
    "step1_variant_a": {{ "subject": "...", "body": "..." }},
    "step1_variant_b": {{ "subject": "...", "body": "..." }},
    "step2_followup": {{ "subject": "...", "body": "..." }},
    "step3_breakup": {{ "subject": "...", "body": "..." }}
}}

CRITICAL RULES - SPARTAN/LACONIC TONE:
1. **Short, direct** - No fluff or unnecessary words
2. **Simple language** - NO corporate jargon (leverage, optimize, streamline, innovative, cutting-edge, etc.)
3. **NO PUNCTUATION AT END** of sentences/CTAs - Drop ALL periods, question marks, exclamation points
4. **5-7 sentences max** - Under 100 words total per email

STEP 1 EMAIL STRUCTURE (Connector Angle):
- **Line 1**: `<p>{{{{icebreaker}}}}</p>` (SSM opener from scraped data)
- **Line 2-3**: <p>Bridge connecting opener to offer (1-2 sentences)</p>
- **Line 4**: <p>Specific outcome with numbers (e.g. "We help clinics add 5-10 premium treatments per month")</p>
- **Line 5**: <p>Easy CTA with NO punctuation (e.g. "Worth exploring" or "Want me to intro you")</p>
- **End with**: `<p>Sent from my iPhone</p>`

VARIANT A vs B ANGLES:
- **Variant A**: Problem-solving angle (acknowledge their pain, offer solution)
- **Variant B**: Opportunity angle (highlight what they're missing, offer access)

FOLLOW-UP RULES (SSM SOP):
- **Step 2 (Day 3)**: EXACTLY "Hey {{{{firstName}}}}, worth intro'ing you" (no punctuation)
- **Step 3 (Day 7)**: EXACTLY "Hey {{{{firstName}}}}, maybe this isn't something you're interested in — wishing you the best." (period only after "best")

EXAMPLE FOR EDMONTON LOCAL KOREAN SKINCARE:

VARIANT A (Problem-solving):
Subject: "Edmonton clinic owners"
Body:
<p>{{{{icebreaker}}}}</p>
<p>Noticed most Edmonton clinics still order Korean skincare from Vancouver with 2-week lead times</p>
<p>I know a local supplier who stocks Korean dermaceutical brands and trains your staff on protocols so you can charge $180-200 per treatment</p>
<p>Worth intro'ing you</p>
<p>Sent from my iPhone</p>

VARIANT B (Opportunity):
Subject: "local Korean skincare"
Body:
<p>{{{{icebreaker}}}}</p>
<p>Saw most Edmonton clinics don't know there's a local Korean dermaceutical supplier with training included</p>
<p>I know someone who helps clinics add Korean specialty treatments that book out 3 weeks in advance</p>
<p>Want me to intro you</p>
<p>Sent from my iPhone</p>

NOW GENERATE THE EMAILS based on this exact structure. Use <p> tags for EACH line.
"""

print("=" * 80)
print("PROMPT SENT TO AI:")
print("=" * 80)
print(prompt)
print("\n" + "=" * 80)
print("AI RESPONSE:")
print("=" * 80)

response = client.chat.completions.create(
    model=os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o"),
    messages=[
        {"role": "system", "content": "You are an expert cold email copywriter specializing in Connector Angle and SSM SOP. Output valid JSON only. Follow Spartan tone rules strictly."},
        {"role": "user", "content": prompt}
    ],
    temperature=0.7,
    response_format={"type": "json_object"}
)

content = json.loads(response.choices[0].message.content)
print(json.dumps(content, indent=2))

print("\n" + "=" * 80)
print("STEP 1 VARIANT A BODY:")
print("=" * 80)
print(content["step1_variant_a"]["body"])

print("\n" + "=" * 80)
print("STEP 1 VARIANT B BODY:")
print("=" * 80)
print(content["step1_variant_b"]["body"])
