#!/usr/bin/env python3
"""
YouTube Video Summarizer
Uses Apify to scrape transcript and LLM to summarize.
"""

import os
import sys
import argparse
from dotenv import load_dotenv
from apify_client import ApifyClient
from openai import AzureOpenAI

load_dotenv()

def get_transcript(video_url: str) -> dict:
    """Scrape YouTube transcript using Apify.

    Returns:
        dict with 'transcript', 'title', and 'url' keys
    """
    apify_token = os.getenv("APIFY_API_KEY")
    if not apify_token:
        print("❌ APIFY_API_KEY not found in .env")
        return {"transcript": "", "title": "Unknown", "url": video_url}

    client = ApifyClient(apify_token)

    print(f"🎬 Fetching transcript for: {video_url}")

    run_input = {
        "videoUrls": [video_url],
        "outputFormat": "text"
    }

    try:
        run = client.actor("scrape-creators/best-youtube-transcripts-scraper").call(run_input=run_input)

        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())

        if not items:
            print("❌ No transcript found")
            return {"transcript": "", "title": "Unknown", "url": video_url}

        transcript = items[0].get('transcript', '') or items[0].get('text', '')
        title = items[0].get('title', 'Unknown')

        print(f"✓ Got transcript for: {title}")
        print(f"✓ Transcript length: {len(transcript)} characters")

        return {
            "transcript": transcript,
            "title": title,
            "url": video_url
        }

    except Exception as e:
        print(f"❌ Error fetching transcript: {e}")
        return {"transcript": "", "title": "Unknown", "url": video_url}

def summarize_transcript(transcript: str, lang: str = "en", video_title: str = "Unknown") -> dict:
    """Summarize transcript using Azure OpenAI.

    Args:
        transcript: Video transcript text
        lang: Language for summary (en, vi)
        video_title: Video title from Apify

    Returns:
        dict with 'summary' and 'title' keys
    """
    azure_key = os.getenv("AZURE_OPENAI_API_KEY")
    azure_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT", "gpt-4o")

    if not azure_key or not azure_endpoint:
        print("❌ Azure OpenAI keys missing")
        return {"summary": "", "title": video_title}

    client = AzureOpenAI(
        api_key=azure_key,
        api_version="2024-02-15-preview",
        azure_endpoint=azure_endpoint
    )

    print(f"🧠 Generating {lang.upper()} summary...")

    # Language-specific prompts
    if lang.lower() == "vi":
        prompt = f"""
Hãy tóm tắt nội dung video YouTube này bằng tiếng Việt một cách CHI TIẾT và ĐẦY ĐỦ.

Yêu cầu:
1. **Chủ đề chính**: Video nói về gì? (1-2 câu giới thiệu)

2. **Điểm chính** (liệt kê CHI TIẾT 5-8 điểm quan trọng):
   - Mỗi điểm cần giải thích CỤ THỂ, KHÔNG chỉ liệt kê
   - Bao gồm ví dụ, con số, hoặc chi tiết cụ thể nếu có trong video
   - Giải thích TẠI SAO điểm này quan trọng

3. **Tóm tắt chi tiết** (4-6 đoạn văn):
   - Đoạn 1: Bối cảnh và mục đích của video
   - Đoạn 2-4: Phân tích sâu từng phần nội dung chính
   - Đoạn 5: Các insight, tips, hoặc lời khuyên cụ thể
   - Đoạn 6: Kết luận và takeaway chính

4. **Key Takeaways** (3-5 câu rút ra bài học/hành động cụ thể):
   - Người xem nên làm gì sau khi xem video này?
   - Áp dụng như thế nào vào thực tế?

LƯU Ý: Tóm tắt phải ĐẦY ĐỦ và CHI TIẾT, giữ lại tất cả thông tin quan trọng, số liệu, ví dụ cụ thể từ transcript.

Transcript:
{transcript[:15000]}
"""
        system_msg = "Bạn là chuyên gia tóm tắt nội dung video một cách CỰC KỲ CHI TIẾT, RÕ RÀNG và ĐẦY ĐỦ bằng tiếng Việt. Bạn không bỏ sót bất kỳ thông tin quan trọng nào."
    else:
        prompt = f"""
Summarize this YouTube video transcript in a clear, concise format.

Structure:
1. **Title/Topic**: What is this video about (1 line)
2. **Key Points**: Main takeaways (bullet points, 3-5 points)
3. **Summary**: 2-3 paragraph summary of the content

Transcript:
{transcript[:15000]}
"""
        system_msg = "You are an expert at summarizing video content clearly and concisely."

    try:
        response = client.chat.completions.create(
            model=azure_deployment,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=3000  # Increased for detailed summaries
        )

        summary = response.choices[0].message.content.strip()
        return {"summary": summary, "title": video_title}

    except Exception as e:
        print(f"❌ Error summarizing: {e}")
        return {"summary": "", "title": video_title}

def main():
    parser = argparse.ArgumentParser(description='Summarize YouTube Video')
    parser.add_argument('--url', required=True, help='YouTube video URL')
    parser.add_argument('--lang', default='vi', choices=['en', 'vi'], help='Summary language (default: vi)')
    parser.add_argument('--output', help='Optional: Save summary to file')

    args = parser.parse_args()

    # Step 1: Get transcript
    video_data = get_transcript(args.url)
    if not video_data['transcript']:
        print("❌ Failed to get transcript")
        return

    # Step 2: Summarize
    result = summarize_transcript(
        video_data['transcript'],
        lang=args.lang,
        video_title=video_data['title']
    )

    if not result['summary']:
        print("❌ Failed to generate summary")
        return

    # Step 3: Display result
    print("\n" + "="*60)
    print("📺 VIDEO SUMMARY")
    print("="*60 + "\n")
    print(f"**Video:** {result['title']}")
    print(f"**URL:** {video_data['url']}")
    print(f"**Language:** {args.lang.upper()}\n")
    print(result['summary'])
    print("\n" + "="*60)

    # Step 4: Save to file if requested
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(f"📺 TÓM TẮT VIDEO YOUTUBE\n\n")
            f.write(f"Video: {result['title']}\n")
            f.write(f"Link: {video_data['url']}\n\n")
            f.write("---\n\n")
            f.write(result['summary'])
            f.write("\n\n---\n\n")
            f.write("🤖 Được tạo tự động bởi Anti-Gravity DO Framework\n")
        print(f"\n✓ Summary saved to: {args.output}")

    return result

if __name__ == '__main__':
    main()
