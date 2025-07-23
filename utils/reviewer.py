"""
レビュー機能 - シナリオの添削とリライトを実行
"""

import google.generativeai as genai
from typing import Dict, List, Optional, Tuple
import re
import time
from dataclasses import dataclass
import json

from config import (
    GEMINI_MODEL, DEFAULT_TEMPERATURE, DEFAULT_MAX_TOKENS,
    RETRY_ATTEMPTS, RETRY_DELAY, NG_EXPRESSIONS, OK_EXPRESSIONS
)

@dataclass
class ReviewResult:
    """レビュー結果を格納するデータクラス"""
    phase: str
    issues: List[Dict[str, str]]
    suggestions: List[str]
    overall_evaluation: str
    rewritten_content: Optional[str] = None
    changes_summary: Optional[str] = None

class ScenarioReviewer:
    """シナリオレビュー機能のメインクラス"""
    
    def __init__(self, api_key: str, temperature: float = DEFAULT_TEMPERATURE, 
                 max_tokens: int = DEFAULT_MAX_TOKENS):
        """
        初期化
        
        Args:
            api_key: Gemini API Key
            temperature: 生成時の創造性パラメータ
            max_tokens: 最大生成トークン数
        """
        genai.configure(api_key=api_key)
        self.generation_config = genai.GenerationConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
        self.model = genai.GenerativeModel(GEMINI_MODEL, generation_config=self.generation_config)
    
    def review_content(self, content: str, phase: str, check_items: List[str],
                      original_source: Optional[str] = None) -> ReviewResult:
        """
        コンテンツをレビューする
        
        Args:
            content: レビュー対象のコンテンツ
            phase: 作業フェーズ
            check_items: チェック項目リスト
            original_source: 元ネタ（オプション）
            
        Returns:
            ReviewResult: レビュー結果
        """
        prompt = self._create_review_prompt(content, phase, check_items, original_source)
        
        # リトライロジック付きでAPI実行
        for attempt in range(RETRY_ATTEMPTS):
            try:
                response = self.model.generate_content(prompt)
                return self._parse_review_response(response.text, phase)
            except Exception as e:
                if attempt < RETRY_ATTEMPTS - 1:
                    time.sleep(RETRY_DELAY)
                    continue
                raise e
    
    def rewrite_content(self, content: str, review_result: ReviewResult) -> ReviewResult:
        """
        レビュー結果に基づいてコンテンツをリライトする
        
        Args:
            content: リライト対象のコンテンツ
            review_result: レビュー結果
            
        Returns:
            ReviewResult: リライト結果を含むレビュー結果
        """
        prompt = self._create_rewrite_prompt(content, review_result)
        
        response = self.model.generate_content(prompt)
        rewritten_content, changes_summary = self._parse_rewrite_response(response.text)
        
        review_result.rewritten_content = rewritten_content
        review_result.changes_summary = changes_summary
        
        return review_result
    
    def check_ng_expressions(self, content: str) -> List[Tuple[str, int]]:
        """
        NGワードをチェックする
        
        Args:
            content: チェック対象のコンテンツ
            
        Returns:
            List[Tuple[str, int]]: NGワードと出現位置のリスト
        """
        found_ng = []
        for ng in NG_EXPRESSIONS:
            positions = [m.start() for m in re.finditer(re.escape(ng), content)]
            for pos in positions:
                found_ng.append((ng, pos))
        return sorted(found_ng, key=lambda x: x[1])
    
    def validate_scenario_length(self, content: str) -> Dict[str, any]:
        """
        シナリオの文字数を検証する
        
        Args:
            content: 検証対象のコンテンツ
            
        Returns:
            Dict: 検証結果
        """
        from config import SCENARIO_MIN_LENGTH, SCENARIO_MAX_LENGTH, SCENARIO_OPTIMAL_LENGTH
        
        length = len(content)
        return {
            "length": length,
            "is_valid": SCENARIO_MIN_LENGTH <= length <= SCENARIO_MAX_LENGTH,
            "is_optimal": abs(length - SCENARIO_OPTIMAL_LENGTH) <= 500,
            "min_length": SCENARIO_MIN_LENGTH,
            "max_length": SCENARIO_MAX_LENGTH,
            "optimal_length": SCENARIO_OPTIMAL_LENGTH
        }
    
    def extract_issues_summary(self, review_result: ReviewResult) -> Dict[str, int]:
        """
        レビュー結果から問題点のサマリーを抽出
        
        Args:
            review_result: レビュー結果
            
        Returns:
            Dict: カテゴリ別の問題数
        """
        summary = {}
        for issue in review_result.issues:
            category = issue.get("category", "その他")
            summary[category] = summary.get(category, 0) + 1
        return summary
    
    def _create_review_prompt(self, content: str, phase: str, 
                             check_items: List[str], original_source: Optional[str]) -> str:
        """レビュー用プロンプトを作成"""
        from .prompts import PromptManager
        pm = PromptManager()
        return pm.create_review_prompt(content, phase, check_items, original_source)
    
    def _create_rewrite_prompt(self, content: str, review_result: ReviewResult) -> str:
        """リライト用プロンプトを作成"""
        from .prompts import PromptManager
        pm = PromptManager()
        return pm.create_rewrite_prompt(content, review_result)
    
    def _parse_review_response(self, response_text: str, phase: str) -> ReviewResult:
        """レビューレスポンスを解析"""
        issues = []
        suggestions = []
        overall_evaluation = ""
        
        # カテゴリと問題点を抽出
        category_pattern = r'【(.+?)】'
        issue_pattern = r'- (.+?)：(.+?)(?:→(.+?))?(?:\n|$)'
        
        current_category = ""
        lines = response_text.split('\n')
        
        for line in lines:
            # カテゴリ検出
            category_match = re.match(category_pattern, line)
            if category_match:
                current_category = category_match.group(1)
                continue
            
            # 問題点検出
            issue_match = re.match(issue_pattern, line)
            if issue_match and current_category:
                location = issue_match.group(1).strip()
                issue = issue_match.group(2).strip()
                suggestion = issue_match.group(3).strip() if issue_match.group(3) else ""
                
                issues.append({
                    "category": current_category,
                    "location": location,
                    "issue": issue,
                    "suggestion": suggestion
                })
                
                if suggestion:
                    suggestions.append(suggestion)
        
        # 全体評価を抽出
        if "全体評価" in response_text or "総評" in response_text:
            eval_start = max(
                response_text.find("全体評価"),
                response_text.find("総評")
            )
            if eval_start > -1:
                overall_evaluation = response_text[eval_start:].split('\n', 2)[-1].strip()
        
        return ReviewResult(
            phase=phase,
            issues=issues,
            suggestions=suggestions,
            overall_evaluation=overall_evaluation
        )
    
    def _parse_rewrite_response(self, response_text: str) -> Tuple[str, str]:
        """リライトレスポンスを解析"""
        # リライト後のテキストと変更点を分離
        if "【リライト後】" in response_text and "【変更点】" in response_text:
            parts = response_text.split("【変更点】")
            rewritten = parts[0].replace("【リライト後】", "").strip()
            changes = parts[1].strip() if len(parts) > 1 else ""
        else:
            # 区切りがない場合は全体をリライト結果とする
            rewritten = response_text.strip()
            changes = "変更点のサマリーは提供されていません。"
        
        return rewritten, changes