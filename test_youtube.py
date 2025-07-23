# test_youtube.py

from youtube_transcript_api import YouTubeTranscriptApi

# 世界的に有名で、複数の字幕が存在することが分かっている動画ID
VIDEO_ID = "7IKab3HcfFk"
print(f"--- ライブラリの基本機能テストを開始します ---")
print(f"--- テスト動画ID: {VIDEO_ID} ---")

try:
    print("\n[ステップ1] 字幕リストの取得を試みます...")
    # この一行が成功するかどうかが最も重要です
    transcript_list = YouTubeTranscriptApi.list_transcripts(VIDEO_ID)

    print(f"  -> 成功！利用可能な字幕が見つかりました。")
    
    # 最初の字幕を取得してみる
    transcript = next(iter(transcript_list))
    
    print("\n[ステップ2] 字幕の中身の取得を試みます...")
    full_text_list = transcript.fetch()
    
    print(f"  -> 成功！字幕データの取得が完了しました。")
    
    print("\n--- テスト結果 ---")
    print("ライブラリは正常に動作しています。問題はStreamlitアプリとの連携部分にある可能性が高いです。")
    print("--------------------")

except Exception as e:
    print(f"\n--- !!! エラーが発生しました !!! ---")
    print(f"エラーの種類: {type(e).__name__}")
    print(f"エラーの詳細: {e}")
    print("\n--- テスト結果 ---")
    print("ライブラリの基本機能が動作していません。")
    print("これは、お使いのPCのネットワーク設定、ファイアウォール、またはセキュリティソフトが原因である可能性が非常に高いです。")
    print("--------------------")