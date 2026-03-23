# LinkedIn Parasite — Tone of Voice Examples

## Instructions
These are real LinkedIn posts that define the writing voice. The AI reads this file at runtime to match the tone.

## Your LinkedIn Posts

### Example 1 — Cold Email Follow-Up Strategy

Most people lose their cold email leads after the prospect already said yes.

Someone replies "yeah, let's book a call" and then the sender writes back "great, let me know what time works for you." Now they're just sitting there waiting. The prospect gets busy, forgets, moves on.

Every additional message you send after that first positive reply will necessarily reduce the total number of people who actually end up on a call with you. Think of it like a sieve—the more steps you add, the more people fall through. So the goal is to compress everything into as few steps as humanly possible.

The moment someone says yes, I assume the booking. I pick a time, I book them in, and I send them both an email reply and a calendar notification simultaneously. Something like: "Hey Peter, thanks so much for getting back to me. I'll book you in for Thursday at 10am—you'll get a calendar notification in a minute. If anything changes, would you mind sending me your calendar as well? Linking mine below for convenience. Look forward to chatting."

What happens when someone gets double-notified with both an email and a calendar invite for a specific time? One of two things. Either they show up, or they respond to reschedule. Both of those outcomes are infinitely better than "let me know what time works" followed by silence.

I also link my own calendar in case the time genuinely doesn't work for them, so they can rebook without having to send me another message. And I ask for their calendar too because it's useful to have for the future. The whole point is minimizing the number of back-and-forth messages required to get from "yes" to "on a call."

On top of that, there are two automations I consider non-negotiable for anyone running cold email. The first sends a follow-up one day before the meeting: something casual like "Hey Sam, really looking forward to our chat tomorrow. I'll be a couple minutes early in case you have the time. No pressure." The second sends two hours before, just a quick human-sounding note confirming you'll be there on time. Both of these need to feel like a real person wrote them rather than a generic template.

Set those two up and your show rate goes up by probably 10-20%, which is enormous when you consider how much money you're already spending on leads and outreach to get someone to say yes in the first place.

### Example 2 — Project to Retainer Framework

If you're doing project-based client work and you're not converting those clients into retainers, here's the framework I'd recommend.

Start with a fixed-price project priced high enough that the client is genuinely committed to the outcome, but low enough that saying yes doesn't feel like a huge risk. You should be converting about 30% of the people you pitch at this level.

Next, crush the project and make sure you overdeliver. The client should be thrilled with what you built for them. This is non-negotiable because nothing that comes next works without genuine trust.

Now this is the part most people skip. When you're inside someone's business building systems for them, you're going to notice a bunch of other things that are broken or inefficient or costing them money…stuff they probably don't even realize.

Right after you deliver the project, while the client is still in the afterglow of great work, put together a big Google doc to map out every way you could improve their business, save them money, or help them generate new revenue. Then give them that roadmap for free whether or not they choose to keep working with you.

About 20% of the people who get that roadmap will convert into an ongoing retainer. And the retainer is where the real money lives. One client at $2K a month for 10 months is $20K from a single relationship, versus grinding through 10 separate projects with 10 separate clients who all need to be found, pitched, onboarded, and managed from scratch.

Even if the initial project was purely back-end admin work, don't limit your roadmap to that. Flag the lead generation gaps, the sales bottlenecks, the front-end stuff that's directly revenue-generating. That's how you transition from being the person who fixed their backend into the person who's actively helping grow their business.

### Example 3 — Agentic Workflows in No-Code

The fastest way to start selling agentic workflows is wrapping them inside the no-code automations you're already building.

I tested this on an email reply system I'd built in n8n — 15 to 20 nodes, 3 to 5 hours of work. Rebuilt it with this method in about two minutes. Same quality output, four or five nodes instead of twenty.

The whole idea is you keep the trigger and the final action in n8n or Make . com — the webhook, the CRM event, the email send, whatever — and then everything in the middle gets handed off to an agent.

Step 1: Set up your trigger in n8n or Make . com. The webhook, the CRM event, whatever kicks things off. Stuff you already know how to build.

Step 2: Set up your final action. Sending the email, updating the record, posting to Slack. Nothing new.

Step 3: All the complex middle stuff (data formatting, knowledge base lookups, AI processing, the nodes that used to take hours to wire up) summarize what that logic needs to do in a prompt. Give that to Claude Code along with a claude . md file that tells it to build a Python endpoint on a serverless platform like Modal.

Step 4: About a minute later, your agent hands you back a URL and a ready-to-use curl command. Paste that into a single HTTP request node in n8n, connect it between your trigger and your final action, and you're done.

Your 20-node workflow is now a 4-node workflow. Still visual. Boxes and arrows the client can follow. Still has built-in error handling and retries. But 90% of the heavy lifting happens inside that one HTTP request.

For clients, nothing changes about the presentation. For you, build time drops from hours to minutes. And Modal is absurdly cheap. I've run thousands of these and still have $3.98 left of my original $5 in credits.
