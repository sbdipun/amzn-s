from flask import Flask, request, jsonify
import requests
import re
import json
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO

app = Flask(__name__)

# ---------- Amazon Prime Route ----------
@app.route('/')
def home():
    return '✅ Scraper is live! Use /scrape?url=<amazon_url> or /airtel?url=<airtel_url>'

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

        if not landscape_image:
            scripts = re.findall(r'<script[^>]*>(.*?)</script>', html, re.DOTALL)
            pattern = re.compile(r'"(https://m\.media-amazon\.com/images/S/pv-target-images/[^"]+\.jpg)"')
            for script in scripts:
                matches = pattern.findall(script)
                if matches:
                    landscape_image = matches[0]
                    break

        if not title:
            title_match = re.search(r'<title>(.*?)</title>', html)
            if title_match:
                title = title_match.group(1).replace(' - Amazon.com', '').strip()

        if title and title.startswith("Watch ") and " | Prime Video" in title:
            title = re.sub(r"^Watch (.*?) \| Prime Video$", r"\1", title)

        if not year:
            badge_match = re.search(
                r'<span[^>]*?aria-label="Released (\d{4})"[^>]*?data-automation-id="release-year-badge"[^>]*?>',
                html
            )
            if badge_match:
                year = badge_match.group(1)

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

# ---------- Airtel Route ----------
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

@app.route('/airtel')
def scrape_airtel():
    url = request.args.get('url')
    if not url or "airtelxstream.in" not in url:
        return jsonify({"error": "Missing or invalid Airtel URL"}), 400

    def clean_image_url(u):
        cleaned = re.sub(r'https://img\.airtel\.tv/unsafe/fit-in/\d+x0/filters:format\(\w+\)/', '', u)
        return cleaned.split('?')[0]

    def get_image_orientation(image_url):
        try:
            response = requests.get(image_url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            img = Image.open(BytesIO(response.content))
            w, h = img.size
            return "Portrait" if h > w else "Landscape" if w > h else "Square"
        except:
            return None

    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, 'html.parser')

        landscape = portrait = title = year = None

        # Landscape image
        banner = soup.find('div', class_='banner-img-wrapper desktop-img')
        if banner:
            img_tag = banner.find('img', class_='cdp-banner-image')
            if img_tag:
                landscape = clean_image_url(img_tag.get('src', ''))

        # Portrait from JSON-LD
        thumbnail_urls = []
        for script in soup.find_all('script', type='application/ld+json'):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get('@type') == 'VideoObject':
                    thumb = data.get('thumbnailUrl')
                    if thumb:
                        if isinstance(thumb, list):
                            thumbnail_urls.extend(thumb)
                        else:
                            thumbnail_urls.append(thumb)
            except:
                continue

        for thumb_url in thumbnail_urls:
            cleaned = clean_image_url(thumb_url)
            if get_image_orientation(cleaned) == "Portrait":
                portrait = cleaned
                break

        # Title and year
        details = soup.find('div', class_='content-details')
        if details:
            t = details.find('h1', id='banner-content-title')
            title = t.text.strip() if t else None
            y = details.find('p', id='banner-content-release-year')
            year = y.text.strip() if y else None

        return jsonify({
            "title": f"{title} - ({year})" if title and year else "N/A - (N/A)",
            "year": year or "N/A",
            "landscape_image": landscape or None,
            "titleshot": portrait or None
        })

    except Exception as e:
        return jsonify({
            "error": "Failed to scrape Airtel",
            "details": str(e)
        }), 500

# SonyLiv

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}
@app.route('/sonyliv')
def scrape_sonyliv():
    url = request.args.get('url')
    if not url or "sonyliv.com" not in url:
        return jsonify({"error": "Missing or invalid SonyLiv URL"}), 400

    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        html = response.text

        landscape = re.search(r'landscape_thumb\s*:\s*"(https?://[^"]+)"', html)
        portrait = re.search(r'portrait_thumb\s*:\s*"(https?://[^"]+)"', html)
        title = re.search(r'<h1 class="revamp-title">\s*(.*?)\s*</h1>', html)
        year = re.search(r'<span class="revamp-metadata">\s*(\d{4})\s*</span>', html)

        return jsonify({
            "title": f"{title.group(1)} - ({year.group(1)})" if title and year else "N/A - (N/A)",
            "year": year.group(1) if year else "N/A",
            "landscape_image": landscape.group(1) if landscape else None,
            "titleshot": portrait.group(1) if portrait else None
        })

    except Exception as e:
        return jsonify({
            "error": "Failed to scrape SonyLiv",
            "details": str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
