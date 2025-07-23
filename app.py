import streamlit as st
import google.generativeai as genai
from datetime import datetime
import json
import pandas as pd
import os
from dotenv import load_dotenv
import hashlib
import time
import re
from typing import List, Dict, Tuple

# 環境変数読み込み
load_dotenv()

# config.pyからインポート
from config import GEMINI_MODEL

# YouTube対応のためのインポート
from utils.youtube_helper import YouTubeHelper

# YouTube字幕機能のインポート（オプション）
try:
    from utils.youtube_transcript import YouTubeTranscriptHelper
    has_transcript = True
except ImportError:
    has_transcript = False

st.set_page_config(
    page_title="2chスカッと系シナリオ添削ツール",
    page_icon="✍️",
    layout="wide"
)

# カスタムCSS for Google Docs風の表示
st.markdown("""
<style>
    .review-comment {
        background-color: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 10px;
        margin: 10px 0;
        border-radius: 4px;
    }
    .review-category {
        font-weight: bold;
        color: #856404;
        margin-bottom: 5px;
    }
    .review-issue {
        color: #721c24;
        margin-bottom: 5px;
    }
    .review-suggestion {
        color: #155724;
        font-style: italic;
    }
    .highlighted-text {
        background-color: #ffeb3b;
        padding: 2px 4px;
        border-radius: 3px;
    }
    .token-info {
        background-color: #e3f2fd;
        padding: 10px;
        border-radius: 5px;
        margin: 10px 0;
    }
</style>
""", unsafe_allow_html=True)

# セッション状態の初期化
if 'review_history' not in st.session_state:
    st.session_state.review_history = []
if 'user_name' not in st.session_state:
    st.session_state.user_name = ""
if 'api_key' not in st.session_state:
    st.session_state.api_key = os.getenv('GEMINI_API_KEY', '')
if 'backup_data' not in st.session_state:
    st.session_state.backup_data = []

# ヘルパー関数
def estimate_tokens(text: str) -> int:
    """テキストのトークン数を推定（簡易版）"""
    # 日本語は1文字≒1トークン、英語は4文字≒1トークンとして概算
    japanese_chars = len(re.findall(r'[ぁ-ん]+|[ァ-ヴー]+|[一-龠]+', text))
    other_chars = len(text) - japanese_chars
    return japanese_chars + (other_chars // 4)

def parse_review_response(response_text: str) -> List[Dict[str, str]]:
    """レビュー結果をパースして構造化"""
    reviews = []
    current_category = ""
    
    lines = response_text.split('\n')
    for line in lines:
        if line.startswith('【') and line.endswith('】'):
            current_category = line[1:-1]
        elif line.startswith('- ') and current_category:
            # 該当箇所：問題点 → 修正案 のパターンを解析
            match = re.match(r'- (.+?)：(.+?)(?:→(.+?))?$', line)
            if match:
                location = match.group(1).strip()
                issue = match.group(2).strip()
                suggestion = match.group(3).strip() if match.group(3) else ""
                
                reviews.append({
                    'category': current_category,
                    'location': location,
                    'issue': issue,
                    'suggestion': suggestion
                })
    
    return reviews

def highlight_issues_in_text(content: str, reviews: List[Dict[str, str]]) -> str:
    """テキスト内の問題箇所をハイライト"""
    highlighted_content = content
    
    for review in reviews:
        location = review['location']
        # 該当箇所を黄色でハイライト
        if location in highlighted_content:
            highlighted_content = highlighted_content.replace(
                location,
                f'<span class="highlighted-text">{location}</span>'
            )
    
    return highlighted_content

def create_backup(data: Dict) -> None:
    """作業内容をバックアップ"""
    backup_entry = {
        'timestamp': datetime.now().isoformat(),
        'data': data
    }
    st.session_state.backup_data.append(backup_entry)
    
    # 最新10件のみ保持
    if len(st.session_state.backup_data) > 10:
        st.session_state.backup_data = st.session_state.backup_data[-10:]

# タイトルとユーザー情報
col_title, col_user = st.columns([3, 1])
with col_title:
    st.title("2chスカッと系シナリオ添削・リライトツール")
with col_user:
    st.session_state.user_name = st.text_input(
        "担当者名", 
        value=st.session_state.user_name,
        placeholder="あなたの名前"
    )

# サイドバー設定
with st.sidebar:
    st.header("⚙️ 設定")
    
    # API Key設定
    api_key = st.text_input(
        "Gemini API Key", 
        type="password",
        value=st.session_state.api_key,
        help="環境変数 GEMINI_API_KEY でも設定可能"
    )
    if api_key:
        st.session_state.api_key = api_key
    
    # 作業フェーズ
    st.header("📝 作業フェーズ")
    phase = st.selectbox(
        "フェーズを選択",
        [
            "プロット添削",
            "プロット修正版添削",
            "シナリオ添削",
            "シナリオ修正版添削",
            "最終リライト"
        ]
    )
    
    # チェック項目
    st.header("✅ チェック項目")
    default_checks = os.getenv('DEFAULT_CHECK_ITEMS', '').split(',') if os.getenv('DEFAULT_CHECK_ITEMS') else []
    
    check_items = {
        "設定の矛盾": st.checkbox("設定の矛盾", value=True),
        "リアリティ": st.checkbox("リアリティ", value=True),
        "スカッと要素": st.checkbox("スカッと要素", value=True),
        "主人公の正当性": st.checkbox("主人公の正当性", value=True),
        "文章構成": st.checkbox("文章構成", value=True),
        "時系列": st.checkbox("時系列", value=True),
        "元ネタとの差別化": st.checkbox("元ネタとの差別化", value=True)
    }
    
    # 詳細設定
    with st.expander("🔧 詳細設定"):
        temperature = st.slider("創造性", 0.0, 1.0, 0.3)
        max_tokens = st.number_input("最大トークン数", 100, 8000, 4000)
    
    # バックアップ機能
    st.header("💾 バックアップ")
    if st.session_state.backup_data:
        st.info(f"バックアップ: {len(st.session_state.backup_data)}件")
        if st.button("バックアップを復元"):
            with st.expander("バックアップ一覧"):
                for i, backup in enumerate(reversed(st.session_state.backup_data)):
                    timestamp = datetime.fromisoformat(backup['timestamp'])
                    if st.button(f"{timestamp.strftime('%Y-%m-%d %H:%M:%S')}", key=f"backup_{i}"):
                        st.session_state.restored_backup = backup['data']
                        st.success("バックアップを復元しました")

# メインエリア
tab1, tab2, tab3, tab4 = st.tabs(["📝 添削・リライト", "📊 統計", "📚 マニュアル", "💾 バックアップ"])

with tab1:
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.header("入力")
        
        # 作業ID生成（トラッキング用）
        work_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{hashlib.md5(str(time.time()).encode()).hexdigest()[:8]}"
        st.caption(f"作業ID: {work_id}")
        
        # 元ネタ入力
        with st.expander("元ネタ（オプション）", expanded=True):
            # YouTube URL入力
            youtube_url = st.text_input(
                "YouTube URL",
                placeholder="https://www.youtube.com/watch?v=...",
                help="元ネタのYouTube動画URLを入力してください"
            )
            
            # YouTube URLが入力されたら情報を表示
            if youtube_url:
                if YouTubeHelper.extract_video_id(youtube_url):
                    video_id = YouTubeHelper.extract_video_id(youtube_url)
                    YouTubeHelper.display_youtube_preview(youtube_url)
                    
                    col_yt1, col_yt2 = st.columns(2)
                    
                    with col_yt1:
                        # 自動的に元ネタテキストを生成
                        if st.button("YouTube情報を元ネタに追加"):
                            youtube_note = YouTubeHelper.create_youtube_note(youtube_url)
                            st.session_state.youtube_note = youtube_note
                            st.success("YouTube情報を追加しました")
                    
                    with col_yt2:
                        # 字幕取得ボタン（オプション）
                        if has_transcript and st.button("字幕を取得"):
                            with st.spinner("字幕を取得中..."):
                                try:
                                    # まず利用可能な字幕を確認
                                    from youtube_transcript_api import YouTubeTranscriptApi
                                    transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)
                                    
                                    available = []
                                    for t in transcript_list:
                                        available.append(f"{t.language} ({t.language_code})")
                                    
                                    if available:
                                        st.info(f"利用可能な字幕: {', '.join(available)}")
                                    
                                    result = YouTubeTranscriptHelper.get_summary(video_id)
                                    if result['success']:
                                        st.session_state.youtube_note = f"""元ネタ動画: {YouTubeHelper.get_video_info(video_id)['title']}
URL: {youtube_url}

【動画の内容（字幕）】
{result['text']}
"""
                                        st.success(f"字幕を取得しました（{result['length']}文字）")
                                    else:
                                        st.error(result['message'])
                                        if not available:
                                            st.warning("この動画には字幕が設定されていません。")
                                        else:
                                            st.info("別の言語の字幕を試すか、自動字幕を有効にしてください。")
                                except Exception as e:
                                    st.error(f"エラーが発生しました: {str(e)}")
                                    st.info("動画が非公開、削除済み、または字幕が無効になっている可能性があります。")

            
            # テキストエリア（YouTube情報または手動入力）
            original_source = st.text_area(
                "元ネタの詳細",
                height=200,
                help="パクリチェックのため、元ネタがある場合は入力してください",
                value=st.session_state.get('youtube_note', st.session_state.get('restored_backup', {}).get('original_source', ''))
            )
            
            # YouTube情報をクリア
            if 'youtube_note' in st.session_state and st.button("YouTube情報をクリア"):
                del st.session_state.youtube_note
                st.rerun()
        
        # 対象コンテンツ入力
        content = st.text_area(
            "添削・リライト対象のコンテンツ",
            height=400,
            placeholder="ここにプロットまたはシナリオを入力してください...",
            value=st.session_state.get('restored_backup', {}).get('content', '')
        )
        
        # 文字数カウントと警告
        if content:
            char_count = len(content)
            estimated_tokens = estimate_tokens(content)
            
            col_count1, col_count2, col_count3 = st.columns(3)
            with col_count1:
                st.metric("文字数", f"{char_count:,}文字")
            with col_count2:
                st.metric("推定トークン", f"{estimated_tokens:,}")
            with col_count3:
                if phase in ["シナリオ添削", "シナリオ修正版添削"]:
                    if 5000 <= char_count <= 7000:
                        st.success("適正文字数")
                    else:
                        st.warning("推奨: 5,000～7,000文字")
    
    with col2:
        st.header("結果")
        
        if st.button("🚀 添削・リライト実行", type="primary", disabled=not api_key or not content):
            if not st.session_state.user_name:
                st.warning("担当者名を入力してください")
            else:
                with st.spinner("処理中..."):
                    try:
                        # バックアップ作成
                        create_backup({
                            'content': content,
                            'original_source': original_source,
                            'phase': phase,
                            'check_items': check_items
                        })
                        
                        # Gemini API設定
                        genai.configure(api_key=api_key)
                        generation_config = genai.GenerationConfig(
                            temperature=temperature,
                            max_output_tokens=max_tokens,
                        )
                        model = genai.GenerativeModel(GEMINI_MODEL, generation_config=generation_config)
                        
                        # プロンプト生成
                        active_checks = [k for k, v in check_items.items() if v]
                        system_prompt = f"""
あなたは2chスカッと系シナリオの添削・リライト専門家です。
{phase}を行ってください。

チェック項目：
{', '.join(active_checks)}

以下の形式で問題点を指摘してください：
【カテゴリ】
- 該当箇所：問題点 → 修正案

具体的な該当箇所（文章の一部）を明記し、問題点と修正案を提示してください。
全体的な評価も最後に追加してください。
"""
                        
                        if phase == "最終リライト":
                            prompt = f"""
{system_prompt}

さらに、以下の点に注意してリライトしてください：
- 冒頭に書き込みの意図を示す一文を追加（報告型/実況型）
- 時制を統一（書き込み時点を意識）
- 分かりやすい文章に
- 主語を明示（スレ主以外が主語の場合）
- 語尾を変化させる
- 漢字にできる部分は漢字に

【対象コンテンツ】
{content}

{"【元ネタ】" + original_source if original_source else ""}

リライト後の全文と、変更点のサマリーを提供してください。
"""
                        else:
                            prompt = f"""
{system_prompt}

【対象コンテンツ】
{content}

{"【元ネタ】" + original_source if original_source else ""}
"""
                        
                        # API実行
                        start_time = time.time()
                        response = model.generate_content(prompt)
                        end_time = time.time()
                        result_text = response.text
                        
                        # トークン使用量の計算（推定）
                        input_tokens = estimate_tokens(prompt)
                        output_tokens = estimate_tokens(result_text)
                        total_tokens = input_tokens + output_tokens
                        processing_time = end_time - start_time
                        
                        # トークン情報表示
                        st.markdown(f"""
                        <div class="token-info">
                            <strong>🔢 トークン使用量</strong><br>
                            入力: {input_tokens:,} | 出力: {output_tokens:,} | 合計: {total_tokens:,}<br>
                            処理時間: {processing_time:.2f}秒
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # 結果表示
                        if phase == "最終リライト":
                            st.subheader("✨ リライト結果")
                            
                            # リライト後のテキストと変更点を分離して表示
                            if "【リライト後】" in result_text and "【変更点】" in result_text:
                                parts = result_text.split("【変更点】")
                                rewritten = parts[0].replace("【リライト後】", "").strip()
                                changes = parts[1].strip() if len(parts) > 1 else ""
                                
                                st.text_area("リライト後", rewritten, height=400)
                                
                                with st.expander("変更点のサマリー"):
                                    st.markdown(changes)
                            else:
                                st.text_area("リライト後", result_text, height=400)
                            
                            # ダウンロードボタン
                            st.download_button(
                                label="📥 リライト結果をダウンロード",
                                data=result_text,
                                file_name=f"rewrite_{work_id}.txt",
                                mime="text/plain"
                            )
                        else:
                            st.subheader("📋 添削結果")
                            
                            # Google Docs風の表示
                            reviews = parse_review_response(result_text)
                            
                            if reviews:
                                # 元のテキストを表示（問題箇所をハイライト）
                                with st.expander("📄 元のテキスト（問題箇所ハイライト）", expanded=True):
                                    highlighted_content = highlight_issues_in_text(content, reviews)
                                    st.markdown(f'<div style="white-space: pre-wrap;">{highlighted_content}</div>', unsafe_allow_html=True)
                                
                                # コメント形式で添削結果を表示
                                st.subheader("💬 添削コメント")
                                for i, review in enumerate(reviews):
                                    st.markdown(f"""
                                    <div class="review-comment">
                                        <div class="review-category">【{review['category']}】</div>
                                        <div class="review-issue">📍 該当箇所: {review['location']}</div>
                                        <div class="review-issue">❌ 問題点: {review['issue']}</div>
                                        {f'<div class="review-suggestion">✅ 修正案: {review["suggestion"]}</div>' if review['suggestion'] else ''}
                                    </div>
                                    """, unsafe_allow_html=True)
                                
                                # 問題点の統計
                                issue_count = len(reviews)
                                category_counts = {}
                                for review in reviews:
                                    cat = review['category']
                                    category_counts[cat] = category_counts.get(cat, 0) + 1
                                
                                st.info(f"💡 合計 {issue_count}件の改善提案があります")
                                
                                # カテゴリ別集計
                                with st.expander("📊 カテゴリ別問題数"):
                                    for cat, count in category_counts.items():
                                        st.write(f"- {cat}: {count}件")
                                
                                # 添削結果のダウンロード
                                st.markdown("---")
                                
                                # 添削結果をテキスト形式に整形
                                download_content = f"""【添削結果】
作業ID: {work_id}
日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
担当者: {st.session_state.user_name}
フェーズ: {phase}

===== 元のテキスト =====
{content}

===== 添削コメント =====
"""
                                for review in reviews:
                                    download_content += f"""
【{review['category']}】
該当箇所: {review['location']}
問題点: {review['issue']}
{f"修正案: {review['suggestion']}" if review['suggestion'] else ''}
---
"""
                                
                                download_content += f"""
===== 問題点の統計 =====
合計: {len(reviews)}件
"""
                                for cat, count in category_counts.items():
                                    download_content += f"- {cat}: {count}件\n"
                                
                                # ダウンロードボタン
                                col_dl1, col_dl2 = st.columns(2)
                                
                                with col_dl1:
                                    st.download_button(
                                        label="📥 添削結果をテキストでダウンロード",
                                        data=download_content,
                                        file_name=f"review_{work_id}.txt",
                                        mime="text/plain"
                                    )
                                
                                with col_dl2:
                                    # JSON形式でもダウンロード可能に
                                    json_data = {
                                        'work_id': work_id,
                                        'timestamp': datetime.now().isoformat(),
                                        'user': st.session_state.user_name,
                                        'phase': phase,
                                        'original_content': content,
                                        'reviews': reviews,
                                        'statistics': category_counts
                                    }
                                    
                                    st.download_button(
                                        label="📥 添削結果をJSONでダウンロード",
                                        data=json.dumps(json_data, ensure_ascii=False, indent=2),
                                        file_name=f"review_{work_id}.json",
                                        mime="application/json"
                                    )
                            else:
                                # 構造化できない場合は通常表示
                                st.markdown(result_text)
                        
                        # 履歴に追加
                        st.session_state.review_history.append({
                            "work_id": work_id,
                            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            "user": st.session_state.user_name,
                            "phase": phase,
                            "content_preview": content[:100] + "...",
                            "char_count": len(content),
                            "token_count": total_tokens,
                            "processing_time": processing_time,
                            "checks": active_checks,
                            "result": result_text,
                            "has_original": bool(original_source)
                        })
                        
                        st.success("✅ 処理が完了しました！")
                        st.balloons()
                        
                    except Exception as e:
                        st.error(f"❌ エラーが発生しました: {str(e)}")
                        st.info("API Keyが正しいか、ネットワーク接続を確認してください。")

with tab2:
    st.header("📊 作業統計")
    
    if st.session_state.review_history:
        # 統計データの集計
        df = pd.DataFrame(st.session_state.review_history)
        
        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
        
        with col_stat1:
            st.metric("総作業数", len(df))
            
        with col_stat2:
            st.metric("作業者数", df['user'].nunique())
            
        with col_stat3:
            avg_chars = df['char_count'].mean()
            st.metric("平均文字数", f"{avg_chars:,.0f}")
            
        with col_stat4:
            if 'token_count' in df.columns:
                total_tokens = df['token_count'].sum()
                st.metric("総トークン使用量", f"{total_tokens:,}")
        
        # フェーズ別集計
        st.subheader("フェーズ別作業数")
        phase_counts = df['phase'].value_counts()
        st.bar_chart(phase_counts)
        
        # 作業履歴テーブル
        st.subheader("作業履歴")
        display_columns = ['timestamp', 'user', 'phase', 'content_preview', 'char_count', 'has_original']
        if 'token_count' in df.columns:
            display_columns.append('token_count')
        
        display_df = df[display_columns]
        column_names = ['日時', '担当者', 'フェーズ', 'コンテンツ', '文字数', '元ネタ有']
        if 'token_count' in df.columns:
            column_names.append('トークン数')
        display_df.columns = column_names
        
        st.dataframe(display_df, use_container_width=True)
        
        # エクスポート
        csv = df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📊 履歴をCSVでダウンロード",
            data=csv,
            file_name=f"review_history_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv"
        )
        
        # 履歴クリア
        if st.button("🗑️ 履歴をクリア", type="secondary"):
            st.session_state.review_history = []
            st.rerun()
    else:
        st.info("まだ作業履歴がありません。")

with tab3:
    st.header("📚 使い方マニュアル")
    
    st.markdown("""
    ### 🔄 作業フロー
    
    1. **プロット添削** 
       - 元ネタと比較しながら問題点を指摘
       - 大まかな流れと設定をチェック
    
    2. **プロット修正版添削**（省略可）
       - 修正されたプロットを再チェック
       - 前回の指摘が反映されているか確認
    
    3. **シナリオ添削**
       - 5,000～7,000文字のシナリオをチェック
       - より詳細な文章表現まで確認
    
    4. **シナリオ修正版添削**（省略可）
       - 修正されたシナリオを再チェック
    
    5. **最終リライト**
       - 完成版として文章を実際に書き換え
       - すぐに使える形に仕上げる
    
    ### ✅ チェックポイント詳細
    
    #### 🔍 設定の矛盾
    - 登場人物の設定（死亡した人物が後で登場等）
    - 時代設定（2011年以前にLINE等）
    - 法的・制度的誤り（内容証明を手渡し等）
    
    #### 🎯 リアリティ
    - 現実離れした設定（人気漫画家、慰謝料1千万円等）
    - 主人公の能力設定（弁護士資格＋空手黒帯等）
    
    #### 💥 スカッと要素
    - 敵役全員への制裁の有無
    - 制裁の十分性（離婚だけでは不十分）
    - 主人公の言い返しの効果
    
    #### ⚖️ 主人公の正当性
    - 主人公側の非の有無
    - 結婚前から分かっていた問題か
    - 適切な行動をとっているか
    - 犯罪まがいの行為をしていないか
    
    #### 📝 文章構成
    - 重複内容の有無
    - 小説的表現（「～のだ」「そう、その時です」等）
    - 時系列の整合性
    - 情報源の明確性
    
    ### ✨ リライトのポイント
    
    1. **冒頭文の追加**
       - 報告型：「～な夫と決着をつけたので聞いてほしい」
       - 実況型：「〇〇な夫のことで相談させてほしい」
    
    2. **文章の調整**
       - 時制の統一（書き込み時点を意識）
       - 長文を避け、シンプルで分かりやすく
       - 主語の明示（スレ主以外が主語の場合）
       - 主語と述語の整合性確認
    
    3. **文体の工夫**
       - 台詞の連続を避け、ナレーションを挟む
       - 同じ語尾の連続を避ける
       - 漢字にできる部分は漢字に変換
    
    ### 💡 Tips
    - 元ネタがある場合は必ず入力（パクリ防止）
    - シナリオは5,000～7,000文字が理想
    - 創作感を出さないよう注意
    - ツッコミどころをなくす
    
    ### 🎥 YouTube元ネタの使い方
    1. YouTube URLを入力
    2. 「YouTube情報を元ネタに追加」をクリック
    3. 字幕取得機能がある場合は「字幕を取得」も可能
    4. 生成されたテキストを編集可能
    """)

with tab4:
    st.header("💾 バックアップ管理")
    
    if st.session_state.backup_data:
        st.info(f"現在 {len(st.session_state.backup_data)} 件のバックアップがあります（最新10件を保持）")
        
        for i, backup in enumerate(reversed(st.session_state.backup_data)):
            timestamp = datetime.fromisoformat(backup['timestamp'])
            with st.expander(f"バックアップ {i+1}: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}"):
                data = backup['data']
                st.write(f"**フェーズ**: {data.get('phase', 'N/A')}")
                st.write(f"**文字数**: {len(data.get('content', '')):,}文字")
                st.write(f"**元ネタあり**: {'はい' if data.get('original_source') else 'いいえ'}")
                
                if st.button(f"このバックアップを復元", key=f"restore_{i}"):
                    st.session_state.restored_backup = data
                    st.success("バックアップを復元しました。「添削・リライト」タブで確認してください。")
                    st.rerun()
    else:
        st.info("バックアップはまだありません。作業を実行すると自動的にバックアップされます。")

# フッター
st.markdown("---")
col_footer1, col_footer2, col_footer3 = st.columns(3)
with col_footer1:
    st.caption("2chスカッと系シナリオ添削・リライトツール v2.1")
with col_footer2:
    st.caption(f"現在の時刻: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
with col_footer3:
    if st.session_state.user_name:
        st.caption(f"ログイン: {st.session_state.user_name}")