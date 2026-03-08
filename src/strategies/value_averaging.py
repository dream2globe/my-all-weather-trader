import pandas as pd
import numpy as np
from typing import Dict, Any
from strategies.base_strategy import BaseStrategy
from config.settings import config
from features.indicators import calculate_va_target

class ValueAveragingStrategy(BaseStrategy):
    """
    가치평균법(Value Averaging) 전략
    - 목표 자산 경로(Target Path) 대비 평가액이 부족하면 매수, 초과하면 관망(또는 일부 매도).
    - [보완1] 적립식 현금 투입(Cash Injection) 지원.
    - [보완2] 상승장 관망을 위한 상단 허용 오차(Tolerance Band) 도입.
    - [보완3] 시스템 리스크 시 현금 고갈을 막는 동적 Max Cap (자산별 기본 할당액 기준).
    """
    def __init__(self, name: str, ticker: str, initial_allocation: float, monthly_growth_rate: float, max_cap_rate: float,
                 tolerance_band: float = 0.0, monthly_injection: float = 0.0,
                 rolling_window_years: int = None, update_frequency_months: int = 6):
        super().__init__(name)
        self.ticker = ticker
        self.initial_allocation = initial_allocation
        self.monthly_growth_rate = monthly_growth_rate # 초기 및 Fallback 용도
        
        self.max_cap_rate = max_cap_rate 
        self.tolerance_band = tolerance_band
        self.monthly_injection = monthly_injection
        
        # 동적 롤링 윈도우 파라미터 갱신용
        self.rolling_window_years = rolling_window_years
        self.update_frequency_months = update_frequency_months
        self.next_update_time = None
        
        # 엔진 실행 중 동적 타겟 트래킹용
        self.current_target_value = self.initial_allocation
        self.last_month = None

    def _recalculate_growth_rate(self, current_time: pd.Timestamp, data: pd.DataFrame):
        """과거 N년의 데이터를 슬라이싱하여 최적의 월 목표 성장률로 내부 파라미터를 동적 업데이트합니다."""
        if self.rolling_window_years is None:
            return
            
        start_date = current_time - pd.DateOffset(years=self.rolling_window_years)
        window_df = data.loc[start_date:current_time]
        
        # 데이터가 너무 짧으면 갱신 포기 (최소 50봉)
        if len(window_df) < 50:
            return
            
        first_price = float(window_df['Close'].iloc[0])
        last_price = float(window_df['Close'].iloc[-1])
        delta_years = (window_df.index[-1] - window_df.index[0]).days / 365.25
        
        if delta_years > 0 and first_price > 0:
            cagr = (last_price / first_price) ** (1 / delta_years) - 1
            monthly_target = (1 + cagr) ** (1/12) - 1
            # 하락장 방어
            if monthly_target <= 0:
                monthly_target = 0.001
                
            self.monthly_growth_rate = monthly_target
            # 전략 모니터링을 위해 print 대신 로거 연결이 좋으나, 전략 레벨에선 간소화 처리

    def precalculate_targets(self, full_data: pd.DataFrame):
        """동적 업데이트로 변경하여 사용하지 않음. 전략 내부 상태로 관리."""
        pass

    def generate_signals(self, 
                         current_time: pd.Timestamp, 
                         data: pd.DataFrame, 
                         portfolio_status: Dict[str, Any]) -> Dict[str, float]:
        
        # 0. 지정된 주기가 도래했는지 확인 후 롤링 윈도우 동적 파라미터 갱신
        if self.rolling_window_years is not None:
            if self.next_update_time is None:
                # 초기 1회 스킵 후 첫 갱신일 예약
                self.next_update_time = current_time + pd.DateOffset(months=self.update_frequency_months)
            elif current_time >= self.next_update_time:
                self._recalculate_growth_rate(current_time, data)
                self.next_update_time = current_time + pd.DateOffset(months=self.update_frequency_months)

        current_price = data.loc[current_time, 'Close']
        current_holdings = portfolio_status['holdings'].get(self.ticker, 0.0)
        current_eval_value = current_holdings * current_price
        
        # 1. 동적 타겟 궤도 업데이트 (적립식 투자 반영)
        current_month = current_time.to_period('M')
        if self.last_month != current_month:
            # 월이 바뀌면: 이전 목표 평가액에 '복리 성장률'을 곱하고 '이번 달 신규 투자금'을 더함
            self.current_target_value = (self.current_target_value * (1 + self.monthly_growth_rate)) + self.monthly_injection
            self.last_month = current_month
        
        # 2. 오차 계산: 현재 평가액이 목표치(Target) 대비 얼마나 부족한지(양수) 넘쳤는지(음수) 확인
        diff_value = self.current_target_value - current_eval_value
        
        # 3. 매수 시그널 (현재 평가액 < 목표액)
        if diff_value > 0:
            # 방어 로직: 1회 최대 매수 금액(Max Cap)은 '해당 자산 배분액'의 N%로 제한 (현금 고갈 방지)
            dynamic_max_buy = self.current_target_value * self.max_cap_rate
            buy_amount = min(diff_value, dynamic_max_buy, portfolio_status['cash'])
            return {self.ticker: buy_amount / current_price} if buy_amount > 0 else {self.ticker: 0.0}
            
        # 4. 매도 시그널 (현재 평가액 > 목표액)
        elif diff_value < 0:
            # 허용 오차 밴드(Tolerance Band)를 설정해 상승 랠리 시 너무 일찍 파는 것을 방지
            exceed_ratio = abs(diff_value) / self.current_target_value
            if exceed_ratio > self.tolerance_band:
                # 밴드를 초과한 '순수 초과분'의 절반(50%)만 매도하여 수익 실현 + 상승 추세 유지
                pure_exceed_value = abs(diff_value) - (self.current_target_value * self.tolerance_band)
                sell_qty = (pure_exceed_value * 0.5) / current_price
                
                # 공매도 방지: 가진 수량 이상으로 팔 수 없음
                actual_sell_qty = min(sell_qty, current_holdings) 
                return {self.ticker: -actual_sell_qty}
            
        # 목표 궤도 허용치 이내 (관망)
        return {self.ticker: 0.0}


class VolatilityTargetingInversePyramid(BaseStrategy):
    """
    MDD 역피라미드 + 변동성 타겟팅 (Inverse Pyramid + Volatility Targeting) 전략
    - 국소 고점 대비 하락장(-15%, -20% 등) 발생 시 대기 현금을 투입해 기하급수적 물타기.
    - 단, 최근 14일 ATR(변동성)이 임계치를 초과하면 극단적 위험 장세로 판단, 보유 물량의 50%를 즉시 현금화하여 방어.
    """
    def __init__(self, name: str, ticker: str, mdd_levels: list[float], invest_ratios: list[float], vol_target: float):
        super().__init__(name)
        self.ticker = ticker
        self.mdd_levels = sorted(mdd_levels, reverse=True) # 예: [-0.15, -0.20, -0.30]
        self.invest_ratios = invest_ratios # 해당 레벨별 투입할 현금 비율
        self.vol_target = vol_target # ATR 변동성 현금화 임계치 (예: 0.05)
        self.purchased_levels = set() # 한 사이클 내에서 이미 진입한 MDD 레벨 추적용
        self.cooldown_until = None # 변동성 회피 후 재진입 쿨다운 타임
        
    def generate_signals(self, 
                         current_time: pd.Timestamp, 
                         data: pd.DataFrame, 
                         portfolio_status: Dict[str, Any]) -> Dict[str, float]:
        
        from features.indicators import calculate_rolling_mdd, calculate_atr
        
        # 1. 쿨다운 기간 체크: 강제 매도 후 일정 기간 동안은 진입 불가
        if self.cooldown_until and current_time < self.cooldown_until:
            return {self.ticker: 0.0}

        # 데이터 슬라이싱 (성능 향상을 위해 최근 60개 봉만 가져옴)
        window_size = 60 * 24 if config.use_hourly_data else 60
        target_df = data.loc[:current_time].tail(window_size)
        
        # 2. 극단적 변동성(ATR) 감지 방어 로직 (방패)
        min_atr_window = 14 * 24 if config.use_hourly_data else 14
        if len(target_df) >= 14: # (최소 14개 봉 이상일 때만 계측 가능)
            current_atr = calculate_atr(target_df, window=min_atr_window).iloc[-1]
            
            # 위험 발동: 현재 변동성이 목표치(vol_target) 초과
            if current_atr > self.vol_target:
                current_holdings = portfolio_status['holdings'].get(self.ticker, 0.0)
                if current_holdings > 0:
                    # 보유량 절반(50%)을 즉시 투매하여 리스크 헤지
                    sell_qty = - (current_holdings * 0.5)
                    # 3일간 쿨다운: 투매 직후 칼날잡기를 막기 위해 강제 휴식 부여
                    self.cooldown_until = current_time + pd.Timedelta(days=3)
                    self.purchased_levels.clear() # 하락사이클 초기화
                    return {self.ticker: sell_qty}
        
        # 3. 역피라미드 (Inverse Pyramid) 물타기 로직 (창)
        current_mdd = calculate_rolling_mdd(target_df, window=window_size).iloc[-1]
        
        # 시세가 전고점을 회복(MDD 0 근접) 시 물타기 사이클 완전 종료
        if current_mdd >= -0.01:
            self.purchased_levels.clear()
            return {self.ticker: 0.0}
            
        signal_qty = 0.0
        current_price = data.loc[current_time, 'Close']
        available_cash = portfolio_status['cash']

        # 하락 폭이 깊어진 순서대로 체크 (예: -20% 트리거가 켜지면 -15%는 통과)
        for i, level in enumerate(self.mdd_levels):
            # MDD가 레벨보다 더 깊게 떨어졌고, 아직 해당 레벨에선 매수한 적 없다면
            if current_mdd <= level and i not in self.purchased_levels:
                # 할당된 현금 비율만큼 투입
                invest_amount = portfolio_status['initial_capital'] * self.invest_ratios[i]
                invest_amount = min(invest_amount, available_cash)
                
                signal_qty += invest_amount / current_price
                self.purchased_levels.add(i)
        
        return {self.ticker: signal_qty}
