"""
YouTube動画の字幕を取得するヘルパー
"""

from youtube_transcript_api import YouTubeTranscriptApi
from typing import Optional, List, Dict
import re

class YouTubeTranscriptHelper:
    """YouTube動画の字幕を取得するヘルパークラス"""
    
    @staticmethod
    def _fetch_and_format_transcript(transcript) -> Optional[str]:
        """Transcriptオブジェクトからテキストを取得し、整形する内部メソッド。失敗した場合はNoneを返す。"""
        try:
            subtitle_data = transcript.fetch()
            if not subtitle_data:
                return None
            
            text_parts = [entry['text'].strip() for entry in subtitle_data if entry['text'].strip()]
            if not text_parts:
                return None
                
            full_text = '\n'.join(text_parts)
            full_text = re.sub(r'\n+', '\n', full_text)
            return full_text
        except Exception as e:
            print(f"警告: 字幕データの中身の取得またはフォーマット中にエラー: {e}")
            return None

    @staticmethod
    def get_transcript(video_id: str, languages: List[str] = ['ja', 'en']) -> Optional[str]:
        """
        動画の字幕を取得。手動字幕、自動生成字幕の順で探し、
        指定言語がなければ利用可能な全ての字幕を試す。
        
        Args:
            video_id: YouTube動画ID
            languages: 優先言語リスト
            
        Returns:
            字幕テキスト or None
        """
        try:
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
            
            candidates = []
            # 優先順位に従って候補リストを作成
            for lang in languages:
                try:
                    candidates.append(transcript_list.find_transcript([lang]))
                except Exception: pass
            for lang in languages:
                try:
                    candidates.append(transcript_list.find_generated_transcript([lang]))
                except Exception: pass
            
            # 残りの全ての字幕も候補に追加
            for t in transcript_list:
                if t not in candidates:
                    candidates.append(t)
            
            print(f"字幕取得を試行します (最大{len(candidates)}件)...")
            
            # 候補を順番に試す
            for i, transcript in enumerate(candidates):
                print(f"  [{i+1}/{len(candidates)}] 試行中: {transcript.language_code} (自動生成: {transcript.is_generated})")
                full_text = YouTubeTranscriptHelper._fetch_and_format_transcript(transcript)
                
                if full_text:
                    print(f"  -> 成功！")
                    return full_text
                else:
                    print(f"  -> 失敗または空データ。次の候補を試します。")
            
            print("エラー: 全ての候補を試しましたが、有効な字幕を取得できませんでした。")
            return None

        except Exception as e:
            print(f"字幕取得プロセス全体でエラーが発生しました: {e}")
            return None
    
    @staticmethod
    def get_summary(video_id: str, max_length: int = 3000) -> Dict[str, any]:
        """
        動画の字幕を取得してサマリー用に整形
        
        Args:
            video_id: YouTube動画ID
            max_length: 最大文字数
            
        Returns:
            サマリー情報
        """
        transcript = YouTubeTranscriptHelper.get_transcript(video_id)
        
        if not transcript:
            return {
                'success': False,
                'message': '字幕を取得できませんでした。手動でのコピー＆ペーストをお試しください。',
                'text': ''
            }
        
        if len(transcript) > max_length:
            transcript = transcript[:max_length] + '...\n（以下省略）'
        
        return {
            'success': True,
            'message': '字幕を取得しました',
            'text': transcript,
            'length': len(transcript)
        }