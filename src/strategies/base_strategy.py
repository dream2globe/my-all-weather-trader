from abc import ABC, abstractmethod
import pandas as pd
from typing import Dict, Any

class BaseStrategy(ABC):
    """
    모든 매매 전략의 상위 추상 클래스
    """
    def __init__(self, name: str, params: Dict[str, Any] = None):
        self.name = name
        self.params = params or {}

    @abstractmethod
    def generate_signals(self, 
                         current_time: pd.Timestamp, 
                         data: pd.DataFrame, 
                         portfolio_status: Dict[str, Any]) -> Dict[str, float]:
        """
        현재 시점(current_time)의 데이터를 기반으로 다음 시점(T+1)에 체결될 매수/매도 시그널을 생성.
        Look-ahead Bias를 피하기 위해 엔진이 current_time의 종가까지만 볼 수 있도록 데이터를 전달함.
        
        Args:
            current_time: 시그널을 생성하는 현재 시간
            data: 과거부터 current_time까지의 데이터
            portfolio_status: 현재 자산 보유량, 버퍼 현금, 평균 단가 등의 포트폴리오 상태
            
        Returns:
            {'Ticker명': 시그널_목표_수량_또는_비중} 형태의 딕셔너리
            양수면 매수, 음수면 매도, 0이면 관망.
        """
        pass
