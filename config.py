"""
設定ファイル - 2chスカッと系シナリオ添削ツール
"""

import os
from typing import Dict, List

# アプリケーション基本設定
APP_NAME = "2chスカッと系シナリオ添削ツール"
APP_VERSION = "2.0.0"
APP_ICON = "✍️"

# 作業フェーズ
WORK_PHASES = [
    "プロット添削",
    "プロット修正版添削",
    "シナリオ添削",
    "シナリオ修正版添削",
    "最終リライト"
]

# デフォルトのチェック項目
DEFAULT_CHECK_ITEMS = {
    "設定の矛盾": True,
    "リアリティ": True,
    "スカッと要素": True,
    "主人公の正当性": True,
    "文章構成": True,
    "時系列": True,
    "元ネタとの差別化": True
}

# チェック項目の詳細説明
CHECK_ITEM_DESCRIPTIONS = {
    "設定の矛盾": [
        "登場人物の設定（死亡した人物が後で登場等）",
        "時代設定（2011年以前にLINE等）",
        "法的・制度的誤り（内容証明を手渡し等）"
    ],
    "リアリティ": [
        "現実離れした設定（人気漫画家、慰謝料1千万円等）",
        "主人公の能力設定（弁護士資格＋空手黒帯等）",
        "非現実的な展開"
    ],
    "スカッと要素": [
        "敵役全員への制裁の有無",
        "制裁の十分性（離婚だけでは不十分）",
        "主人公の言い返しの効果"
    ],
    "主人公の正当性": [
        "主人公側の非の有無",
        "結婚前から分かっていた問題か",
        "適切な行動をとっているか",
        "犯罪まがいの行為をしていないか"
    ],
    "文章構成": [
        "重複内容の有無",
        "小説的表現（「～のだ」「そう、その時です」等）",
        "語尾の単調さ",
        "台詞とナレーションのバランス"
    ],
    "時系列": [
        "時系列の整合性",
        "情報源の明確性",
        "時制の統一"
    ],
    "元ネタとの差別化": [
        "設定の差別化（家族構成、年齢等）",
        "ストーリー展開の独自性",
        "パクリと思われない程度の変更"
    ]
}

# 文字数制限
SCENARIO_MIN_LENGTH = 5000
SCENARIO_MAX_LENGTH = 7000
SCENARIO_OPTIMAL_LENGTH = 6000

# Gemini API設定
GEMINI_MODEL = "gemini-2.0-flash"
DEFAULT_TEMPERATURE = 0.3
DEFAULT_MAX_TOKENS = 4000
MAX_TEMPERATURE = 1.0
MIN_TEMPERATURE = 0.0

# プロンプト設定
PROMPT_TIMEOUT = 60  # seconds
RETRY_ATTEMPTS = 3
RETRY_DELAY = 2  # seconds

# ファイル設定
EXPORT_ENCODING = "utf-8-sig"
HISTORY_FILE_PREFIX = "review_history"
REWRITE_FILE_PREFIX = "rewrite"

# UI設定
LAYOUT = "wide"
SIDEBAR_STATE = "expanded"
THEME = "light"

# 統計設定
STATS_REFRESH_INTERVAL = 5  # minutes
MAX_HISTORY_RECORDS = 1000

# セキュリティ設定
REQUIRE_USER_NAME = True
MASK_API_KEY = True
LOG_API_CALLS = False

# 環境変数から設定を読み込む関数
def load_env_config():
    """環境変数から設定を読み込む"""
    config = {}
    
    # API Key
    config['GEMINI_API_KEY'] = os.getenv('GEMINI_API_KEY', '')
    
    # デフォルトチェック項目
    env_checks = os.getenv('DEFAULT_CHECK_ITEMS', '')
    if env_checks:
        config['DEFAULT_CHECK_ITEMS'] = env_checks.split(',')
    
    # その他の設定
    config['DEBUG_MODE'] = os.getenv('DEBUG_MODE', 'False').lower() == 'true'
    config['LOG_LEVEL'] = os.getenv('LOG_LEVEL', 'INFO')
    
    return config

# NGワード設定（小説的表現）
NG_EXPRESSIONS = [
    "のだ。",
    "のだった。",
    "していたんだ。",
    "そう、その時です。",
    "地球の裏側まで届くような",
    "～であった。",
    "～なのであった。"
]

# OKな表現例
OK_EXPRESSIONS = [
    "だった。",
    "した。",
    "その瞬間",
    "すると",
    "そして"
]

# エラーメッセージ
ERROR_MESSAGES = {
    "no_api_key": "Gemini API Keyが設定されていません。",
    "no_content": "添削・リライト対象のコンテンツを入力してください。",
    "no_user_name": "担当者名を入力してください。",
    "api_error": "API実行中にエラーが発生しました。",
    "network_error": "ネットワーク接続を確認してください。",
    "invalid_length": f"シナリオは{SCENARIO_MIN_LENGTH:,}～{SCENARIO_MAX_LENGTH:,}文字で作成してください。"
}

# 成功メッセージ
SUCCESS_MESSAGES = {
    "review_complete": "添削が完了しました！",
    "rewrite_complete": "リライトが完了しました！",
    "export_complete": "エクスポートが完了しました！",
    "history_cleared": "履歴をクリアしました。"
}

# プロンプトテンプレート設定
PROMPT_TEMPLATES = {
    "review": "review_prompt",
    "rewrite": "rewrite_prompt",
    "final_check": "final_check_prompt"
}

# バリデーション設定
VALIDATION_RULES = {
    "min_content_length": 100,
    "max_content_length": 10000,
    "min_original_length": 50,
    "max_api_retries": 3
}