"""
未來學分析框架 — 台灣未來學標準術語
Taiwan Futures Studies Methodology Framework

術語依據：
- 鄭明宗《未來方法論》繁體中文譯本
- Inayatullah 因果分層分析法（CLA）標準中譯
- Schwartz 情節規劃（Scenario Planning）台灣學術用語
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class SignalStrength(Enum):
    """浮現議題強度（取代「弱訊號」舊稱）"""
    EMERGING_ISSUE = "浮現議題"  # 邊緣群體的異常行為，1-5% 人群
    TREND = "趨勢"               # 5-20% 人群已出現
    DRIVING_FORCE = "驅力"       # 主流現象 >20%，已成形的驅動力


class TimeHorizon(Enum):
    """時間視野層"""
    NEAR = "近期（0-1年）"
    MID = "中期（1-5年）"
    FAR = "遠期（5-10年）"


class ScenarioType(Enum):
    """情節類型 — Schwartz 情節規劃框架（取代「情境」舊稱）"""
    BEST_CASE = "最佳想象"          # Best Case
    WORST_CASE = "最糟想象"         # Worst Case
    BUSINESS_AS_USUAL = "如常情節"  # Business as Usual (BAU)，基線未來
    OUTLIER = "驟變情節"            # Outlier，低概率高衝擊的突發轉折


class FutureType(Enum):
    """未來錐三類未來（Futures Cone）"""
    POSSIBLE = "可能的未來"   # Possible：邏輯上可發生
    PLAUSIBLE = "似乎的未來"  # Plausible：沿現有驅力可預期的發展
    PREFERRED = "渴望的未來"  # Preferred：利益相關者希望實現的未來


@dataclass
class EmergingIssue:
    """
    浮現議題（Emerging Issue）
    取代舊稱「弱訊號（Weak Signal）」，為台灣未來學標準術語。
    指模擬中邊緣群體的異常行為，可能預示重大轉折。
    """
    description: str
    evidence: str              # 來自模擬的 Agent 行為證據
    strength: SignalStrength
    potential_impact: str      # 若議題放大，可能的未來走向
    time_horizon: TimeHorizon = TimeHorizon.MID


@dataclass
class Scenario:
    """
    情節（Scenario）
    Schwartz 情節規劃框架中的一條未來路徑。
    注意：台灣未來學將 scenario 譯為「情節」而非「情境」。
    """
    name: str
    scenario_type: ScenarioType
    future_type: FutureType
    probability: float           # 0-1 概率估計
    description: str
    driving_forces: List[str]    # 推動此情節的關鍵驅力
    key_indicators: List[str]    # 此情節的觀察指標
    horizon: TimeHorizon


@dataclass
class CausalLayeredAnalysis:
    """
    因果分層分析法（Causal Layered Analysis，CLA）
    Inayatullah 提出，台灣標準譯名。
    四層次從表面現象到深層文化結構。
    """
    litany: str         # 表象層（Litany）：可見事件與統計數字
    systemic: str       # 系統層（Systemic）：社會／政治／技術系統
    worldview: str      # 世界觀（Worldview）：信念與價值體系
    myth_metaphor: str  # 迷思／隱喻層（Myth/Metaphor）：深層文化結構


@dataclass
class SteepAnalysis:
    """STEEP 分析維度"""
    social: str = ""         # 社會（Social）
    technological: str = ""  # 科技（Technological）
    environmental: str = ""  # 環境（Environmental）
    economic: str = ""       # 經濟（Economic）
    political: str = ""      # 政治（Political）

    def to_dict(self) -> Dict[str, str]:
        return {
            "社會": self.social,
            "科技": self.technological,
            "環境": self.environmental,
            "經濟": self.economic,
            "政治": self.political,
        }


@dataclass
class FuturesCone:
    """
    未來錐（Futures Cone / Cone of Plausibility）
    包含三類未來的預測範疇。
    """
    possible: List[str] = field(default_factory=list)   # 可能的未來
    plausible: List[str] = field(default_factory=list)  # 似乎的未來
    preferred: List[str] = field(default_factory=list)  # 渴望的未來


@dataclass
class FuturesAnalysis:
    """
    完整的未來學分析框架輸出結構。

    整合：
    - Inayatullah 因果分層分析法（CLA）
    - Schwartz 情節規劃（Scenario Planning）
    - 未來錐（Futures Cone / Cone of Plausibility）
    - STEEP 分析維度
    """
    driving_forces: List[str]               # 關鍵驅力
    emerging_issues: List[EmergingIssue]    # 浮現議題（取代「弱訊號」）
    scenarios: List[Scenario]               # 多種未來情節
    steep: SteepAnalysis                    # STEEP 維度分析
    cla: Optional[CausalLayeredAnalysis]    # 因果分層分析（可選）
    futures_cone: FuturesCone               # 未來錐（可能／似乎／渴望）

    def to_report_context(self) -> str:
        """將未來學分析摘要轉換為報告生成的上下文提示文字"""
        parts = []

        if self.driving_forces:
            parts.append(f"【驅力】{', '.join(self.driving_forces)}")

        if self.emerging_issues:
            parts.append(f"【浮現議題數量】{len(self.emerging_issues)} 項")
            for issue in self.emerging_issues:
                parts.append(
                    f"  - {issue.description}"
                    f"（強度：{issue.strength.value}）"
                )

        if self.scenarios:
            parts.append(f"【情節數量】{len(self.scenarios)} 條")
            for sc in self.scenarios:
                parts.append(
                    f"  - {sc.name}"
                    f"（{sc.scenario_type.value}，概率：{sc.probability:.0%}）"
                )

        if self.cla:
            parts.append("【CLA 表象層摘要】")
            parts.append(f"  {self.cla.litany[:80]}...")

        return "\n".join(parts)

    def get_outlier_scenarios(self) -> List[Scenario]:
        """取得所有驟變情節（Outlier Scenarios）"""
        return [s for s in self.scenarios if s.scenario_type == ScenarioType.OUTLIER]

    def get_preferred_futures(self) -> List[str]:
        """取得渴望的未來清單"""
        return self.futures_cone.preferred
