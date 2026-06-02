# decoder.py
import requests
import re
import time
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ===== YAHAN TUMHARA EXISTING DECODER KA CODE AAYEGA =====
import requests
import re
import time
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# ===== UTILITY =====
def fetch_text(url, referer=None, method="GET", body=None, cookies=None):
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-US,en;q=0.5",
    }
    if referer:
        headers["Referer"] = referer
    try:
        if method == "POST":
            resp = requests.post(url, headers=headers, data=body, cookies=cookies, timeout=15)
        else:
            resp = requests.get(url, headers=headers, cookies=cookies, timeout=15)
        return resp.text
    except:
        return None

def fetch_with_redirect(url, referer=None):
    """Fetch and return final URL after redirects."""
    headers = {"User-Agent": USER_AGENT}
    if referer:
        headers["Referer"] = referer
    try:
        resp = requests.get(url, headers=headers, timeout=15, allow_redirects=True)
        return resp.text, resp.url
    except:
        return None, url

def make_full_url(url):
    """Ensure URL has full https://driveseed.org prefix."""
    if not url:
        return None
    if url.startswith('/file/'):
        return f"https://driveseed.org{url}"
    if url.startswith('file/'):
        return f"https://driveseed.org/{url}"
    if 'driveseed.org' not in url and url.startswith('/'):
        return f"https://driveseed.org{url}"
    return url

# ===== STEP 1: Extract ALL links from ModPro =====
def extract_all_links(modpro_url, referer_url):
    """
    Extract ALL links from ModPro page including:
    - Direct SID links
    - JavaScript-generated links (from script tags)
    - Encoded/hidden links
    """
    print(f"  📄 ModPro: {modpro_url.split('/')[-1]}")
    
    html = fetch_text(modpro_url, referer=referer_url)
    if not html:
        return []
    
    soup = BeautifulSoup(html, 'html.parser')
    all_links = []
    seen_urls = set()
    
    # Method 1: Direct SID links in <a> tags
    for a in soup.find_all('a', href=True):
        href = a['href']
        text = a.text.strip()
        
        if '?sid=' in href:
            skip_texts = ['Episodes.ModPro.Blog', 'ModPro.Blog', 'our comment section', '']
            if text not in skip_texts and href not in seen_urls:
                all_links.append({"server": text, "url": href, "source": "direct"})
                seen_urls.add(href)
    
    # Method 2: Extract from JavaScript (script tags)
    for script in soup.find_all('script'):
        if script.string:
            # Find encoded SID links or base64
            sid_matches = re.findall(r'https?://[^\s"\']+\?sid=[^\s"\']+', script.string)
            for url in sid_matches:
                if url not in seen_urls:
                    all_links.append({"server": "Generated Link", "url": url, "source": "script"})
                    seen_urls.add(url)
            
            # Find base64 encoded links
            b64_matches = re.findall(r'["\']([A-Za-z0-9+/=]{20,})["\']', script.string)
            for b64 in b64_matches:
                try:
                    import base64
                    decoded = base64.b64decode(b64).decode('utf-8')
                    if '?sid=' in decoded or 'driveseed.org' in decoded:
                        if decoded not in seen_urls:
                            all_links.append({"server": "Decoded Link", "url": decoded, "source": "base64"})
                            seen_urls.add(decoded)
                except:
                    pass
    
    # Method 3: Extract from onclick/data attributes
    for elem in soup.find_all(attrs={"onclick": True}):
        onclick = elem.get('onclick', '')
        urls = re.findall(r'https?://[^\s"\']+', onclick)
        for url in urls:
            if ('?sid=' in url or 'driveseed' in url) and url not in seen_urls:
                all_links.append({"server": elem.text.strip() or "Click Link", "url": url, "source": "onclick"})
                seen_urls.add(url)
    
    # Method 4: Look for data-url/data-href attributes
    for elem in soup.find_all():
        for attr in ['data-url', 'data-href', 'data-link']:
            val = elem.get(attr)
            if val and ('?sid=' in val or 'driveseed' in val):
                if val not in seen_urls:
                    all_links.append({"server": elem.text.strip() or "Data Link", "url": val, "source": "data-attr"})
                    seen_urls.add(val)
    
    print(f"    ✅ Found {len(all_links)} links (direct: {sum(1 for l in all_links if l['source']=='direct')}, script: {sum(1 for l in all_links if l['source']=='script')}, other: {sum(1 for l in all_links if l['source'] not in ['direct','script'])})")
    return all_links

# ===== STEP 2: Resolve SID → Driveleech =====
def resolve_sid_to_driveleech(sid_url, referer_url):
    """2-step POST to resolve SID to Driveleech URL."""
    html = fetch_text(sid_url, referer=referer_url)
    if not html:
        return None
    
    # Check for rate limiting
    if "Error 1015" in html or "rate limited" in html:
        print(f"    ⚠️ Rate limited, waiting 3s...")
        time.sleep(3)
        html = fetch_text(sid_url, referer=referer_url)
        if not html:
            return None
    
    soup = BeautifulSoup(html, 'html.parser')
    form = soup.select_one("#landing")
    if not form:
        return None
    
    wp_http = form.find("input", {"name": "_wp_http"})
    action = form.get("action")
    if not wp_http or not action:
        return None
    
    # Step 1 POST
    html2 = fetch_text(action, referer=sid_url, method="POST", body={"_wp_http": wp_http.get("value")})
    if not html2:
        return None
    
    soup2 = BeautifulSoup(html2, 'html.parser')
    form2 = soup2.select_one("#landing")
    if not form2:
        return None
    
    action2 = form2.get("action")
    wp_http2 = form2.find("input", {"name": "_wp_http2"})
    token = form2.find("input", {"name": "token"})
    if not all([action2, wp_http2, token]):
        return None
    
    # Step 2 POST
    html3 = fetch_text(action2, referer=sid_url, method="POST", body={
        "_wp_http2": wp_http2.get("value"),
        "token": token.get("value")
    })
    if not html3:
        return None
    
    # Extract cookie and link
    cookie_match = re.search(r"s_343\('([^']+)',\s*'([^']+)'", html3)
    link_match = re.search(r'c\.setAttribute\("href",\s*"([^"]+)"\)', html3)
    if not cookie_match or not link_match:
        return None
    
    cookie_name = cookie_match.group(1)
    cookie_value = cookie_match.group(2)
    final_path = link_match.group(1)
    
    origin = f"{urlparse(sid_url).scheme}://{urlparse(sid_url).netloc}"
    final_url = urljoin(origin, final_path)
    
    # Fetch with cookie
    cookies = {cookie_name: cookie_value}
    html4 = fetch_text(final_url, referer=sid_url, cookies=cookies)
    if not html4:
        return None
    
    soup4 = BeautifulSoup(html4, 'html.parser')
    meta_refresh = soup4.find("meta", {"http-equiv": "refresh"})
    if meta_refresh:
        content = meta_refresh.get("content", "")
        url_match = re.search(r'url=(.+)', content, re.IGNORECASE)
        if url_match:
            return url_match.group(1).strip().strip('"').strip("'")
    
    return None

# ===== STEP 3: Resolve to /file/ format =====
def resolve_to_file_format(driveseed_url):
    """Resolve Driveleech to /file/XXXXX format with full URL."""
    
    if not driveseed_url:
        return None
    
    if '/file/' in driveseed_url:
        return make_full_url(driveseed_url)
    
    if 'moviesmod.wiki' in driveseed_url:
        return None
    
    html, final_url = fetch_with_redirect(driveseed_url)
    
    if not html:
        return make_full_url(driveseed_url)
    
    if '/file/' in final_url:
        return make_full_url(final_url)
    
    soup = BeautifulSoup(html, 'html.parser')
    
    # Meta refresh
    meta = soup.find("meta", {"http-equiv": "refresh"})
    if meta:
        content = meta.get("content", "")
        url_match = re.search(r'url=(.+)', content, re.IGNORECASE)
        if url_match:
            redirect = url_match.group(1).strip().strip('"').strip("'")
            if '/file/' in redirect:
                return make_full_url(redirect)
            if 'driveseed.org' in redirect:
                return resolve_to_file_format(redirect)
    
    # JavaScript redirect
    for pattern in [
        r'window\.location\s*=\s*["\']([^"\']*/file/[^"\']*)["\']',
        r'window\.location\.href\s*=\s*["\']([^"\']*/file/[^"\']*)["\']',
        r'location\.replace\(["\']([^"\']*/file/[^"\']*)["\']\)',
    ]:
        match = re.search(pattern, html)
        if match:
            return make_full_url(match.group(1))
    
    # Direct /file/ link in HTML
    file_match = re.search(r'(?:https?://driveseed\.org)?(/file/[^\s"\'<>]+)', html)
    if file_match:
        return make_full_url(file_match.group(0))
    
    # Follow redirect chain
    try:
        resp = requests.get(driveseed_url, headers={
            "User-Agent": USER_AGENT,
            "Referer": "https://driveseed.org/"
        }, allow_redirects=True, timeout=10)
        
        if '/file/' in resp.url:
            return make_full_url(resp.url)
        
        final_soup = BeautifulSoup(resp.text, 'html.parser')
        final_meta = final_soup.find("meta", {"http-equiv": "refresh"})
        if final_meta:
            content = final_meta.get("content", "")
            url_match = re.search(r'url=(.+)', content, re.IGNORECASE)
            if url_match:
                return make_full_url(url_match.group(1))
    except:
        pass
    
    return make_full_url(driveseed_url)

# ===== COMPLETE PIPELINE =====
def extract_moviesmod_files(page_url):
    """Complete pipeline returning FULL https://driveseed.org/file/XXXXX URLs."""
    
    print(f"\n{'='*60}")
    print(f"🎬 MoviesMod → Driveseed Full URLs")
    print(f"{'='*60}")
    print(f"📄 {page_url}\n")
    
    html = fetch_text(page_url)
    if not html:
        return {}
    
    soup = BeautifulSoup(html, 'html.parser')
    content = soup.select_one(".thecontent") or soup
    
    all_results = {}
    
    buttons = content.find_all('a', class_='maxbutton')
    
    for btn in buttons:
        btn_url = btn.get('href', '')
        
        if 'modpro.blog' not in btn_url:
            continue
        
        prev_header = btn.find_previous(['h3', 'h4'])
        quality = prev_header.text.strip() if prev_header else "Unknown"
        btn_type = btn.text.strip()
        
        section_name = f"{quality} | {btn_type}"
        
        print(f"📁 {quality}")
        print(f"   🔗 {btn_url}")
        print(f"   ┃")
        
        # Step 1: Get ALL links (including JS-generated)
        all_links = extract_all_links(btn_url, page_url)
        
        if not all_links:
            print(f"   ┖ ❌ No links found\n")
            continue
        
        # Step 2 & 3: Resolve to full /file/ URLs
        resolved_files = []
        
        for link in all_links:
            # If already a /file/ link, use directly
            if '/file/' in link['url']:
                file_url = make_full_url(link['url'])
                resolved_files.append({
                    "episode": link['server'],
                    "url": file_url
                })
                continue
            
            # If SID link, resolve through pipeline
            if '?sid=' in link['url']:
                driveleech = resolve_sid_to_driveleech(link['url'], btn_url)
                
                if not driveleech:
                    continue
                
                if 'moviesmod.wiki' in driveleech:
                    continue
                
                file_url = resolve_to_file_format(driveleech)
                
                if file_url and '/file/' in file_url:
                    resolved_files.append({
                        "episode": link['server'],
                        "url": file_url
                    })
            
            time.sleep(0.2)
        
        if resolved_files:
            print(f"   ┖ 🔓 {len(resolved_files)} files:")
            for f in resolved_files:
                print(f"      • {f['episode']}")
                print(f"        {f['url']}")
        else:
            print(f"   ┖ ⚠️ No files resolved")
        
        print()
        
        all_results[section_name] = {
            "modpro_url": btn_url,
            "files": resolved_files
        }
        
        time.sleep(0.5)  # Delay between sections
    
    return all_results


# ==========================================
# RUN
# ==========================================
if __name__ == "__main__":
    results = extract_moviesmod_files(
        "https://moviesmod.farm/download-if-wishes-could-kill-season-1-hindi-480p-720p-1080p/"
    )
    
    print("\n" + "="*60)
    print("FINAL CLICKABLE LINKS")
    print("="*60)
    
    for section, data in results.items():
        print(f"\n📁 {section}")
        for f in data['files']:
            print(f"   • {f['episode']}")
            print(f"     {f['url']}")
# Tumhare jo bhi functions hain - fetch_text, extract_all_links, 
# resolve_sid_to_driveleech, resolve_to_file_format, extract_moviesmod_files
# Sab copy-paste karo idhar

# NOTE: extract_moviesmod_files function ko modify karna hoga
# Jo return karega: structured data with season, quality, single_links, batch_links

def extract_moviesmod_files(page_url):
    """
    Modified version - returns structured data
    """
    # Tumhara existing code yahan aayega
    # But return format yeh rakhna:
    return {
        "title": "Show/Movie Name",
        "type": "movie" or "single_season" or "multi_season",
        "seasons": {
            "S01": {
                "480p": {
                    "single": ["link1", "link2"],
                    "batch": "batch_link"
                },
                "720p": {
                    "single": ["link1", "link2"],
                    "batch": "batch_link"
                }
            }
        }
    }
