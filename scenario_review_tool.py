import google.generativeai as genai
from typing import List, Dict, Optional
import json
import re
from dataclasses import dataclass
from enum import Enum

class WorkPhase(Enum):
    PLOT_REVIEW = "プロット添削"
    PLOT_REVISION_REVIEW = "プロット修正版添削"
    SCENARIO_REVIEW = "シナリオ添削"
    SCENARIO_REVISION_REVIEW = "シナリオ修正版添削"
    FINAL_REWRITE = "最終リライト"

@dataclass
class ReviewPoint:
    category: str
    location: str
    issue: str
    suggestion: str

class ScenarioReviewTool:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        self.system_prompt = self._load_system_prompt()
    
    def _load_system_prompt(self) -> str:
        return """
あなたは2chスカッと系シナリオの添削・リライト専門家です。
以下の観点で厳密にチェックしてください：

1. 設定の矛盾
- 登場人物の設定（死亡した人物が後で登場等）
- 時代設定（2011年以前にLINE等）
- 法的・制度的誤り（内容証明を手渡し等）

2. リアリティ
- 現実離れした設定（人気漫画家、慰謝料1千万円等）
- 主人公の能力設定

3. スカッと要素
- 敵役全員への制裁の有無
- 制裁の十分性（離婚だけでは不十分）
- 主人公の言い返しの効果

4. 主人公の正当性
- 主人公側の非の有無
- 結婚前から分かっていた問題か
- 適切な行動をとっているか

5. 文章構成
- 重複内容
- 小説的表現（「～のだ」「そう、その時です」等）
- 時系列の整合性
- 情報源の明確性

リライト時は上記に加えて：
- 冒頭文の追加（報告型/実況型）
- 時制の統一
- 分かりやすい文章
- 主語の明示
- 語尾の変化
"""
    
    def review_content(self, content: str, phase: WorkPhase, 
                      original_source: Optional[str] = None) -> List[ReviewPoint]:
        """コンテンツをレビューし、問題点を抽出"""
        
        prompt = f"""
以下の{phase.value}を行ってください。

【対象コンテンツ】
{content}

{"【元ネタ】" + original_source if original_source else ""}

JSON形式で以下の構造で問題点を列挙してください：
{{
  "issues": [
    {{
      "category": "カテゴリ名",
      "location": "該当箇所",
      "issue": "問題点",
      "suggestion": "修正案"
    }}
  ]
}}
"""
        
        response = self.model.generate_content(
            self.system_prompt + "\n\n" + prompt
        )
        
        try:
            result = json.loads(response.text)
            return [ReviewPoint(**issue) for issue in result["issues"]]
        except:
            # JSONパースエラー時は文字列解析
            return self._parse_text_response(response.text)
    
    def _parse_text_response(self, text: str) -> List[ReviewPoint]:
        """テキスト形式のレスポンスを解析"""
        issues = []
        current_category = ""
        
        lines = text.split('\n')
        for line in lines:
            if line.startswith('【') and line.endswith('】'):
                current_category = line[1:-1]
            elif line.startswith('- '):
                parts = line[2:].split('：', 1)
                if len(parts) == 2:
                    location, issue_and_suggestion = parts
                    if '→' in issue_and_suggestion:
                        issue, suggestion = issue_and_suggestion.split('→', 1)
                    else:
                        issue = issue_and_suggestion
                        suggestion = ""
                    
                    issues.append(ReviewPoint(
                        category=current_category,
                        location=location.strip(),
                        issue=issue.strip(),
                        suggestion=suggestion.strip()
                    ))
        
        return issues
    
    def rewrite_content(self, content: str, review_points: List[ReviewPoint]) -> str:
        """レビューポイントに基づいてコンテンツをリライト"""
        
        issues_text = "\n".join([
            f"- {point.category}: {point.location} - {point.issue} → {point.suggestion}"
            for point in review_points
        ])
        
        prompt = f"""
以下のコンテンツを、指摘された問題点を修正してリライトしてください。

【元のコンテンツ】
{content}

【修正すべき問題点】
{issues_text}

【リライト時の注意点】
- 冒頭に書き込みの意図を示す一文を追加
- 時制を統一（書き込み時点を意識）
- 長文を避け、シンプルで分かりやすく
- 主語を明示（スレ主以外が主語の場合）
- 台詞の連続を避け、ナレーションを挟む
- 同じ語尾の連続を避ける
- 漢字にできる部分は漢字に

リライトした全文を出力してください。
"""
        
        response = self.model.generate_content(
            self.system_prompt + "\n\n" + prompt
        )
        
        return response.text
    
    def process_document(self, content: str, phase: WorkPhase, 
                        original_source: Optional[str] = None) -> Dict:
        """ドキュメントを処理し、結果を返す"""
        
        if phase == WorkPhase.FINAL_REWRITE:
            # 最終リライトの場合は、まずレビューしてからリライト
            review_points = self.review_content(content, phase, original_source)
            rewritten_content = self.rewrite_content(content, review_points)
            
            return {
                "phase": phase.value,
                "review_points": [vars(point) for point in review_points],
                "rewritten_content": rewritten_content
            }
        else:
            # その他のフェーズはレビューのみ
            review_points = self.review_content(content, phase, original_source)
            
            return {
                "phase": phase.value,
                "review_points": [vars(point) for point in review_points],
                "rewritten_content": None
            }

# 使用例
if __name__ == "__main__":
    # APIキーを設定
    tool = ScenarioReviewTool("YOUR_GEMINI_API_KEY")
    
    # サンプルコンテンツ
    sample_content = """
    私（28歳）と夫（30歳）は結婚3年目。
    義父は他界していて、義母と同居していました。
    ある日、夫が浮気していることが発覚。
    相手は夫の同僚でした。
    私は証拠を集めて、内容証明を手渡しで渡しました。
    その後、義両親が私を責めてきて...
    """
    
    # プロット添削
    result = tool.process_document(
        content=sample_content,
        phase=WorkPhase.PLOT_REVIEW,
        original_source="元ネタのURL等"
    )
    
    print(json.dumps(result, ensure_ascii=False, indent=2))