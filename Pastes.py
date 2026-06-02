# pastes.py
import requests
import json

def create_paste(title, content, subscribe_text="@Sseries_Area"):
    """
    Create paste on pastys.pages.dev
    """
    # Full content with subscribe at bottom
    full_content = content + f"\n\n{'='*40}\n✅ Subscribe - {subscribe_text}"
    
    try:
        # Adjust API endpoint as per your pastys setup
        response = requests.post(
            "https://pastys.pages.dev/api/create",
            json={
                "title": title,
                "content": full_content,
                "language": "text",
                "expiry": "7d"
            },
            timeout=15
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get("url")
    except Exception as e:
        print(f"Paste creation failed: {e}")
    
    # Fallback to rentry.co
    try:
        response = requests.post(
            "https://rentry.co/api/new",
            json={"content": full_content, "edit_code": "moviesmod_bot"},
            timeout=15
        )
        if response.status_code == 200:
            return f"https://rentry.co/{response.json()['url']}"
    except:
        pass
    
    return None

def format_episode_list(episodes, quality_name):
    """
    Format episodes for paste page
    episodes: list of {"name": "file.mkv [size]", "url": "https://..."}
    """
    lines = [f"{quality_name} - Episodes", "="*40, ""]
    
    for ep in episodes:
        lines.append(ep["name"])
        lines.append(f"🔗 {ep['url']}")
        lines.append("")
    
    return "\n".join(lines)

def format_batch_list(batch_name, batch_url):
    """
    Format batch file for paste page
    """
    return f"Batch/Zip File\n{'='*40}\n\n{batch_name}\n🔗 {batch_url}"
