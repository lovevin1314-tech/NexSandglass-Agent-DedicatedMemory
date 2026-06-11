"""Search and download Liu Haocun interview audio from Bilibili."""
import json
import subprocess
import sys

def search_bilibili():
    """Search Bilibili for Liu Haocun interviews."""
    cmd = [
        "yt-dlp",
        "--encoding", "utf-8",
        "--proxy", "http://127.0.0.1:1086",
        "--dump-json",
        "--no-download",
        "https://search.bilibili.com/all?keyword=刘浩存+采访",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        videos = []
        for line in result.stdout.strip().split("\n"):
            if not line:
                continue
            try:
                d = json.loads(line)
                title = d.get("title", "")
                # Clean HTML tags
                title = title.replace("<em class=\"keyword\">", "").replace("</em>", "")
                vid = d.get("id", "")
                dur = d.get("duration", 0)
                view = d.get("view_count", 0)
                url = f"https://www.bilibili.com/video/{vid}"
                videos.append({"title": title, "url": url, "duration": dur, "views": view})
            except:
                pass
        
        # Sort by views (most popular first)
        videos.sort(key=lambda x: x["views"], reverse=True)
        
        for i, v in enumerate(videos[:10]):
            mins = v["duration"] // 60
            secs = v["duration"] % 60
            print(f"[{i+1}] {v['title']}")
            print(f"    链接: {v['url']}")
            print(f"    时长: {mins}:{secs:02d} | 播放: {v['views']}")
            print()
        
        return videos
    except Exception as e:
        print(f"Search error: {e}")
        return []

if __name__ == "__main__":
    videos = search_bilibili()
    if videos:
        print(f"\n共找到 {len(videos)} 个视频")
        print("\n推荐下载（声音清晰、适合克隆的）：")
        print("  1. 采访类（对话清晰）")
        print("  2. 快问快答类（语速自然）")
        print("  3. 央视/Vlog类（音质好）")
