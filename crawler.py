import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import os
import time
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet

visited = set()

def scrape_page(url, domain, image_folder="images"):
    """Fetch page content, extract text, links, images, and download images."""
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        if response.status_code != 200:
            return None, []

        soup = BeautifulSoup(response.text, "html.parser")
        title = soup.title.string.strip() if soup.title else "No Title"
        text = " ".join([p.get_text().strip() for p in soup.find_all("p")])

        # Extract and download images
        images = []
        if not os.path.exists(image_folder):
            os.makedirs(image_folder)

        for img in soup.find_all("img", src=True):
            img_url = urljoin(url, img["src"])
            images.append(img_url)

            # Save image locally
            try:
                img_data = requests.get(img_url, timeout=5).content
                img_name = os.path.basename(urlparse(img_url).path) or f"image_{int(time.time())}.jpg"
                img_path = os.path.join(image_folder, img_name)

                with open(img_path, "wb") as f:
                    f.write(img_data)
            except Exception as e:
                print(f"⚠️ Could not download image {img_url}: {e}")

        # Extract internal links (for further crawling)
        links = []
        all_links = []
        for a in soup.find_all("a", href=True):
            link = urljoin(url, a["href"])
            all_links.append(link)
            if urlparse(link).netloc == domain and link not in visited:
                links.append(link)

        return {
            "url": url,
            "title": title,
            "content": text,
            "images": images,
            "all_links": all_links
        }, links

    except Exception as e:
        print(f"❌ Error scraping {url}: {e}")
        return None, []

def crawl(start_url, max_pages=20, max_depth=2):
    """Crawl website up to given depth and page limit."""
    domain = urlparse(start_url).netloc
    to_visit = [(start_url, 0)]
    results = []

    while to_visit and len(results) < max_pages:
        url, depth = to_visit.pop(0)
        if url in visited or depth > max_depth:
            continue
        visited.add(url)

        page_data, links = scrape_page(url, domain)
        if page_data:
            results.append(page_data)
            print(f"✅ Scraped: {url}")

            # Add new links to crawl queue
            for link in links:
                if link not in visited:
                    to_visit.append((link, depth + 1))

        time.sleep(1)  # polite crawling

    return results

def save_json(data, filename="output.json"):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
    print(f"📁 Data saved to {filename}")

def save_pdf(data, filename="output.pdf"):
    doc = SimpleDocTemplate(filename, pagesize=A4)
    styles = getSampleStyleSheet()
    content = []

    for page in data:
        content.append(Paragraph(f"<b>URL:</b> {page['url']}", styles["BodyText"]))
        content.append(Paragraph(f"<b>Title:</b> {page['title']}", styles["Heading2"]))
        content.append(Paragraph(page["content"][:1500] + "...", styles["BodyText"]))

        if page["images"]:
            content.append(Paragraph("<b>Images:</b>", styles["BodyText"]))
            for img in page["images"][:5]:
                content.append(Paragraph(img, styles["BodyText"]))

        if page["all_links"]:
            content.append(Paragraph("<b>Links:</b>", styles["BodyText"]))
            for lnk in page["all_links"][:10]:
                content.append(Paragraph(lnk, styles["BodyText"]))

        content.append(Spacer(1, 20))

    doc.build(content)
    print(f"📁 Data saved to {filename}")

if __name__ == "__main__":
    start_url = "https://www.python.org"  # 🔹 change this
    scraped_data = crawl(start_url, max_pages=30, max_depth=2)

    # Save outputs
    save_json(scraped_data, "website_data.json")
    save_pdf(scraped_data, "website_data.pdf")
