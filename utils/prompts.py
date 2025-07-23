"""
プロンプト管理 - レビューとリライト用のプロンプトを生成
"""

from typing import List, Optional, Dict
from config import CHECK_ITEM_DESCRIPTIONS

class PromptManager:
    """プロンプト生成と管理を行うクラス"""
    
    def __init__(self):
        self.base_system_prompt = """
あなたは2chスカッと系シナリオの添削・リライト専門家です。
創作であることがバレないよう、リアリティがあり、読者がスカッとする内容に仕上げることが目的です。
"""
    
    def create_review_prompt(self, content: str, phase: str, 
                           check_items: List[str], original_source: Optional[str] = None) -> str:
        """
        レビュー用のプロンプトを生成
        
        Args:
            content: レビュー対象のコンテンツ
            phase: 作業フェーズ
            check_items: チェック項目リスト
            original_source: 元ネタ（オプション）
            
        Returns:
            str: 生成されたプロンプト
        """
        # チェック項目の詳細を構築
        check_details = self._build_check_details(check_items)
        
        prompt = f"""{self.base_system_prompt}

【作業フェーズ】
{phase}

【チェック項目と詳細】
{check_details}

【指示】
以下の形式で問題点を指摘してください：

【カテゴリ名】
- 該当箇所：問題点 → 修正案

各カテゴリごとに問題点を列挙し、具体的な修正案を提示してください。
最後に「全体評価」として、作品全体の印象と改善すべき主要なポイントをまとめてください。

【対象コンテンツ】
{content}

{self._add_original_source(original_source)}
"""
        return prompt
    
    def create_rewrite_prompt(self, content: str, review_result: any) -> str:
        """
        リライト用のプロンプトを生成
        
        Args:
            content: リライト対象のコンテンツ
            review_result: レビュー結果
            
        Returns:
            str: 生成されたプロンプト
        """
        # 問題点のサマリーを作成
        issues_summary = self._summarize_issues(review_result.issues)
        
        prompt = f"""{self.base_system_prompt}

【作業フェーズ】
最終リライト

【修正すべき問題点】
{issues_summary}

【リライト時の必須要件】
1. 冒頭に書き込みの意図を示す一文を追加
   - 報告型：「～な夫と決着をつけたので聞いてほしい」など
   - 実況型：「〇〇な夫のことで相談させてほしい」など

2. 文章の調整
   - 時制を統一（いつ書き込んでいるか意識）
   - 長文を避け、シンプルで分かりやすく
   - 主語を明示（スレ主以外が主語の場合）
   - 主語と述語の整合性確認

3. 文体の工夫
   - 台詞の連続を避け、ナレーションを挟む
   - 同じ語尾の連続を避ける（「～だった。」が続かないよう工夫）
   - 漢字にできる部分は漢字に変換

4. NGワードの排除
   - 「～のだ。」「～していたんだ。」などの小説的表現を使わない
   - 「そう、その時です。」などの演出的な表現を避ける

【出力形式】
以下の形式で出力してください：

【リライト後】
（リライトした全文をここに記載）

【変更点】
（主な変更点を箇条書きでまとめる）

【対象コンテンツ】
{content}
"""
        return prompt
    
    def create_final_check_prompt(self, content: str) -> str:
        """
        最終チェック用のプロンプトを生成
        
        Args:
            content: チェック対象のコンテンツ
            
        Returns:
            str: 生成されたプロンプト
        """
        prompt = f"""{self.base_system_prompt}

【作業フェーズ】
最終確認

【確認項目】
1. 冒頭文が適切に追加されているか
2. 時制が統一されているか
3. 小説的表現が残っていないか
4. スカッと要素が十分か
5. 全体の流れが自然か

以下のコンテンツを最終確認し、問題があれば指摘してください。
問題がなければ「問題なし」と回答してください。

【対象コンテンツ】
{content}
"""
        return prompt
    
    def _build_check_details(self, check_items: List[str]) -> str:
        """チェック項目の詳細を構築"""
        details = []
        for item in check_items:
            if item in CHECK_ITEM_DESCRIPTIONS:
                desc_list = CHECK_ITEM_DESCRIPTIONS[item]
                desc_text = "\n  ".join([f"・{desc}" for desc in desc_list])
                details.append(f"■ {item}\n  {desc_text}")
            else:
                details.append(f"■ {item}")
        
        return "\n\n".join(details)
    
    def _add_original_source(self, original_source: Optional[str]) -> str:
        """元ネタを追加"""
        if original_source:
            return f"""
【元ネタ】
{original_source}

※パクリと思われない程度に設定を変更し、独自性を持たせること
"""
        return ""
    
    def _summarize_issues(self, issues: List[Dict[str, str]]) -> str:
        """問題点をサマリー化"""
        if not issues:
            return "特に大きな問題点はありませんが、より良い作品にするため全体的にブラッシュアップしてください。"
        
        summary_by_category = {}
        for issue in issues:
            category = issue.get("category", "その他")
            if category not in summary_by_category:
                summary_by_category[category] = []
            summary_by_category[category].append(
                f"- {issue['location']}: {issue['issue']}"
            )
        
        summary_text = []
        for category, issue_list in summary_by_category.items():
            summary_text.append(f"【{category}】")
            summary_text.extend(issue_list)
            summary_text.append("")
        
        return "\n".join(summary_text)
    
    def get_example_prompts(self) -> Dict[str, str]:
        """サンプルプロンプトを取得"""
        return {
            "プロット添削": self.create_review_prompt(
                "サンプルプロット...",
                "プロット添削",
                ["設定の矛盾", "リアリティ", "スカッと要素"],
                "元ネタのURL..."
            ),
            "最終リライト": self.create_rewrite_prompt(
                "サンプルシナリオ...",
                type('ReviewResult', (), {
                    'issues': [
                        {"category": "設定の矛盾", "location": "冒頭", "issue": "義父が死亡と後で登場"}
                    ]
                })()
            )
        }