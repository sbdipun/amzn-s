from flask import Flask, request, jsonify
import requests
import re
import json

app = Flask(__name__)

@app.route('/')
def home():
    return '✅ Amazon Scraper is live! Use /scrape?url=https://...'

@app.route('/scrape')
def scrape_amazon():
    url = request.args.get('url')
    if not url or "amazon" not in url:
        return jsonify({"error": "Missing or invalid 'url' param"}), 400

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.amazon.com/",
    }

    try:
        response = requests.get(url, headers=headers, timeout=10)
        html = response.text if response.status_code == 200 else ""

        landscape_image = titleshot = title = year = None

        # JSON block extraction
        data_match = re.search(r'var\s+metaData\s*=\s*({.*?});', html, re.DOTALL)
        if not data_match:
            data_match = re.search(r'data:\s*({.*?})\s*,\s*onLoad', html, re.DOTALL)

        if data_match:
            try:
                json_data = json.loads(data_match.group(1))
                title = json_data.get('title') or json_data.get('titleText', {}).get('value')
                year = json_data.get('releaseYear') or json_data.get('releaseYearText', {}).get('value')
                if 'images' in json_data:
                    titleshot = json_data['images'].get('titleshot')
            except Exception:
                pass

        # Fallback landscape image
        if not landscape_image:
            scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
            pattern = re.compile(r'"(https://m\.media-amazon\.com/images/S/pv-target-images/[^"]+\.jpg)"')
            for script in scripts:
                matches = pattern.findall(script)
                if matches:
                    landscape_image = matches[0]
                    break

        # Fallback title from <title>
        if not title:
            title_match = re.search(r'<title>(.*?)</title>', html)
            if title_match:
                title = title_match.group(1).replace(' - Amazon.com', '').strip()

        if title and title.startswith("Watch ") and " | Prime Video" in title:
            title = re.sub(r"^Watch (.*?) \| Prime Video$", r"\1", title)

        # Year from aria-label if missing
        if not year:
            badge_match = re.search(
                r'<span[^>]*?aria-label="Released (\d{4})"[^>]*?data-automation-id="release-year-badge"[^>]*?>',
                html
            )
            if badge_match:
                year = badge_match.group(1)

        # Fallback titleshot
        if not titleshot:
            titleshot_match = re.search(r'"titleshot":"(https://[^"]+)"', html)
            if titleshot_match:
                titleshot = titleshot_match.group(1)

        return jsonify({
            "title": f"{title} - ({year})" if title and year else "N/A - (N/A)",
            "year": year or "N/A",
            "landscape_image": landscape_image or None,
            "titleshot": titleshot or None
        })

    except Exception as e:
        return jsonify({ "error": "Failed to scrape", "details": str(e) }), 500
