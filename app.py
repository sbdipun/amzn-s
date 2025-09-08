from flask import Flask, request, jsonify
import requests
import re
import json
from bs4 import BeautifulSoup
from PIL import Image
from io import BytesIO
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

app = Flask(__name__)

# ---------- Amazon Prime Route ----------
@app.route('/')
def home():
    return '✅ Scraper is live! Use /scrape?url=<amazon_url> or /airtel?url=<airtel_url> or /sonyliv?url=<airtel_url>'

@app.route('/scrape')
def scrape_amazon():
    url = request.args.get('url')
    if not url or "amazon" not in url:
        return jsonify({"error": "Missing or invalid 'url' param"}), 400

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.amazon.com/",
        "sec-ch-ua-platform": "Windows",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-site",
    }
    
    PROXY = {
    "https": "https://x6DzSR6XnGeLnBLk32UPvjWg:CFcqTXQDxKybUf6qAHTmSxpW@in-mum.prod.surfshark.com:443"
    }

    try:
        response = requests.get(url, headers=headers, proxies=PROXY, timeout=10)
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


PROXY = {
    "https": "https://x6DzSR6XnGeLnBLk32UPvjWg:CFcqTXQDxKybUf6qAHTmSxpW@in-mum.prod.surfshark.com:443"
}

BASE_IMAGE_URL = "https://qqcdnpictest.mxplay.com/"

@app.route('/mxplayer', methods=['GET'])
def mxplayer():
    target_url = request.args.get('url')
    if not target_url:
        return jsonify({"error": "Missing `url` query parameter"}), 400

    try:
        response = requests.get(target_url, proxies=PROXY, timeout=10)
        response.raise_for_status()
        html_content = response.text

        mxs_start_marker = 'window.__mxs__ = '
        start_index = html_content.find(mxs_start_marker)

        if start_index == -1:
            return jsonify({"error": "window.__mxs__ object not found"})

        json_start_index = html_content.find('{', start_index + len(mxs_start_marker))
        if json_start_index == -1:
            return jsonify({"error": "Opening brace not found after mxs marker"})

        # Find matching closing brace
        brace_count = 0
        end_index = -1
        for i in range(json_start_index, len(html_content)):
            if html_content[i] == '{':
                brace_count += 1
            elif html_content[i] == '}':
                brace_count -= 1
            if brace_count == 0:
                end_index = i
                break

        if end_index == -1:
            return jsonify({"error": "Could not find end of JSON block"})

        mxs_json_str = html_content[json_start_index : end_index + 1]
        mxs_data = json.loads(mxs_json_str)

        # Try to extract movie ID from the URL
        match = re.search(r'watch-.*?-([a-f0-9]{32})', target_url)
        if not match:
            return jsonify({"error": "Could not extract movie ID from URL"})
        movie_id = match.group(1)

        entities_data = mxs_data.get("entities", {})
        movie_info = entities_data.get(movie_id)
        if not movie_info:
            return jsonify({"error": f"Movie ID '{movie_id}' not found in data"})

        title = movie_info.get("title")
        release_date = movie_info.get("releaseDate")
        year = release_date.split('-')[0] if release_date else "Unknown"

        images = []
        for img in movie_info.get("imageInfo", []):
            original_url = img.get("url")
            if img.get("type") == "landscape":
                img_url = BASE_IMAGE_URL + original_url.replace("320x180", "3840x2160")
                images.append({"type": "landscape", "url": img_url})
            elif img.get("type") == "portrait_large":
                img_url = BASE_IMAGE_URL + original_url.replace("320x480", "640x960")
                images.append({"type": "portrait_large", "url": img_url})

        return jsonify({
            "title": title,
            "year": year,
            "images": images
        })

    except requests.RequestException as e:
        return jsonify({"error": "Failed to fetch page", "details": str(e)}), 500
    except json.JSONDecodeError as e:
        return jsonify({"error": "Failed to parse JSON", "details": str(e)}), 500

@app.route('/zee5')
def scrape_zee5():

    input_text = request.args.get('id') or request.args.get('url')
    if not input_text:
        return jsonify({"error": "Missing 'url' or 'id' parameter"}), 400

    def is_url(text):
        return bool(re.search(r"https?://", text))

    def extract_zee5_id(url):
        pattern = r"zee5\.com\/(?:movies|web-series|tv-shows)\/details\/[^\/]+\/([0-9a-z-]+)"
        match = re.search(pattern, url, re.IGNORECASE)
        return match.group(1) if match else None

    def get_content_type(text):
        if "/movies/" in text:
            return "movie"
        elif "/web-series/" in text or "/tv-shows/" in text:
            return "tvshow"
        else:
            return "tvshow"

    if is_url(input_text):
        content_id = extract_zee5_id(input_text)
        content_type = get_content_type(input_text)
    else:
        content_id = input_text
        content_type = get_content_type(input_text)

    if not content_id:
        return jsonify({"error": "Invalid ZEE5 URL or ID"}), 400

    url = f"https://gwapi.zee5.com/content/details/{content_id}?translation=en&country=IN"
    headers = {
        'x-access-token': 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJwbGF0Zm9ybV9jb2RlIjoiV2ViQCQhdDM4NzEyIiwiaXNzdWVkQXQiOiIyMDI1LTA4LTA3VDA3OjQ3OjIxLjU2N1oiLCJwcm9kdWN0X2NvZGUiOiJ6ZWU1QDk3NSIsInR0bCI6ODY0MDAwMDAsImlhdCI6MTc1NDU1Mjg0MX0.X2abRQ_3N5U_Wu2jw4KFy7C2gPGcfr8UOHvTJJ6ydyA',
        'origin': 'https://www.zee5.com',
        'referer': 'https://www.zee5.com/',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36'
    }
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        release_date = data.get("release_date", "")
        year = release_date.split("-")[0] if release_date else "N/A"
        image = data.get("image", {})
        image_cover = image.get("cover")
        image_list = image.get("list")
        base_url = "https://akamaividz.zee5.com/image/upload/resources/"
        portrait = f"{base_url}{content_id}/portrait/{image_cover}.jpg" if image_cover else None
        landscape = f"{base_url}{content_id}/list/{image_list}.jpg" if image_list else None
        return jsonify({
            "title": f"{data.get('title', 'N/A')} - ({year})",
            "year": year,
            "landscape_image": landscape,
            "portrait_image": portrait
        })
    except Exception as e:
        return jsonify({"error": "Failed to fetch ZEE5 data", "details": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
