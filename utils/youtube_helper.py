"""
YouTube動画情報取得ヘルパー
"""

import re
import requests
from typing import Optional, Dict
import streamlit as st

class YouTubeHelper:
    """YouTube動画の情報を取得するヘルパークラス"""
    
    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """
        YouTube URLから動画IDを抽出
        
        Args:
            url: YouTube URL
            
        Returns:
            動画ID or None
        """
        # 様々なYouTube URLパターンに対応
        patterns = [
            r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\n?#]+)',
            r'youtube\.com\/watch\?.*v=([^&\n?#]+)',
            r'youtu\.be\/([^&\n?#]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None
    
    @staticmethod
    def get_video_info(video_id: str) -> Dict[str, str]:
        """
        動画IDから基本情報を取得（APIキー不要の簡易版）
        
        Args:
            video_id: YouTube動画ID
            
        Returns:
            動画情報の辞書
        """
        info = {
            'video_id': video_id,
            'url': f'https://www.youtube.com/watch?v={video_id}',
            'embed_url': f'https://www.youtube.com/embed/{video_id}',
            'thumbnail': f'https://img.youtube.com/vi/{video_id}/maxresdefault.jpg',
            'title': 'YouTube動画',
            'description': ''
        }
        
        # oEmbedを使用してタイトルを取得（APIキー不要）
        try:
            oembed_url = f'https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json'
            response = requests.get(oembed_url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                info['title'] = data.get('title', 'YouTube動画')
                info['author'] = data.get('author_name', '')
        except:
            pass
        
        return info
    
    @staticmethod
    def create_youtube_note(url: str) -> str:
        """
        YouTube URLから元ネタ用のノートを作成
        
        Args:
            url: YouTube URL
            
        Returns:
            フォーマットされた元ネタテキスト
        """
        video_id = YouTubeHelper.extract_video_id(url)
        if not video_id:
            return f"元ネタ動画: {url}"
        
        info = YouTubeHelper.get_video_info(video_id)
        
        note = f"""元ネタ動画: {info['title']}
URL: {info['url']}
投稿者: {info.get('author', '不明')}

※この動画を参考にしていますが、設定や詳細は大幅に変更しています。
"""
        return note
    
    @staticmethod
    def display_youtube_preview(url: str) -> None:
        """
        StreamlitでYouTube動画のプレビューを表示
        
        Args:
            url: YouTube URL
        """
        video_id = YouTubeHelper.extract_video_id(url)
        if video_id:
            info = YouTubeHelper.get_video_info(video_id)
            
            col1, col2 = st.columns([1, 2])
            with col1:
                st.image(info['thumbnail'], use_column_width=True)
            with col2:
                st.write(f"**タイトル**: {info['title']}")
                st.write(f"**投稿者**: {info.get('author', '不明')}")
                st.write(f"**URL**: {info['url']}")
        else:
            st.warning("有効なYouTube URLを入力してください")