import pandas as pd
import numpy as np
import logging
from typing import Dict, List, Any
from config.settings import config
from strategies.base_strategy import BaseStrategy

class BacktestEngine:
    """
    Look-ahead Bias를 피하며 포트폴리오를 시뮬레이션하는 결합 엔진.
    """
    def __init__(self, data: Dict[str, pd.DataFrame], strategies: List[BaseStrategy], logger: logging.Logger):
        self.data = data # 티커별로 동기화된 마스터 타임라인 DataFrame 들 (Open, High, Low, Close, Volume)
        self.strategies = strategies
        self.logger = logger
        
        # 포트폴리오 초기 상태
        self.status = {
            'initial_capital': config.initial_investment,
            'cash': config.initial_investment,
            'holdings': {t: 0.0 for t in self.data.keys()},
            'avg_prices': {t: 0.0 for t in self.data.keys()}
        }
        
        # 백테스트 성과 및 거래 기록장
        self.history = []
        self.trades_log = []
        
        # 마스터 타임라인 추출
        self.timeline = list(self.data.values())[0].index

    def run(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        self.logger.info("Starting Backtest Engine...")
        
        # T일(current_time)에 계산된 시그널을 T+1일(next_time) 시가(Open)에 체결하기 위한 지연 변수
        pending_signals = {}
        
        for i, current_time in enumerate(self.timeline):
            # 1. 이전 턴(T-1)에서 예약된 시그널이 있다면, 현재 턴(T) 시가(Open)에 체결 시도 
            # (데이터 누수를 방지하는 핵심 로직)
            if pending_signals:
                self._execute_trades(current_time, pending_signals)
                pending_signals.clear()
            
            # 2. 현재 턴(T) 종가(Close) 기준으로 다음 턴(T+1)을 위한 새로운 시그널 생성
            # (각 전략 객체에 과거부터 현재 시점까지 슬라이싱된 데이터만 전달)
            for strategy in self.strategies:
                sliced_data = {
                    ticker: df.loc[:current_time] 
                    for ticker, df in self.data.items() 
                    if (ticker in df.columns) or (getattr(df, 'name', None) == ticker) or True
                }
                
                # 티커별 DataFrame 중 자기 자신에게 필요한 것만 전달 (간소화를 위해 티커 하나만 다룬다 가정)
                # 실제 구현에서는 전략 인스턴스가 담당 티커를 속성으로 가져서 그 데이터만 뽑는다.
                if hasattr(strategy, 'ticker'):
                    target_df = sliced_data[strategy.ticker]
                    # 시그널 생성 (예: {'SPY': 10.0, 'KRW-BTC': 0.05})
                    signals = strategy.generate_signals(current_time, target_df, self.status)
                    
                    for t, qty in signals.items():
                        pending_signals[t] = pending_signals.get(t, 0.0) + qty

            # 3. 매일(혹은 매시간) 평가액 기록 (종가 기준)
            self._record_history(current_time)

        self.logger.info("Backtest Finished.")
        result_df = pd.DataFrame(self.history)
        result_df.set_index('Date', inplace=True)
        
        trades_df = pd.DataFrame(self.trades_log)
        if not trades_df.empty:
            trades_df.set_index('Date', inplace=True)
            
        return result_df, trades_df

    def _execute_trades(self, execution_time: pd.Timestamp, signals: Dict[str, float]):
        """예약된 시그널을 실제 환경 제약(소수점 불가, 현금 부족, 수수료, 슬리피지) 하에 체결"""
        
        for ticker, target_qty in signals.items():
            if target_qty == 0:
                continue
                
            # 시가(Open)를 체결가로 활용. 슬리피지(Slippage) 페널티 부여
            # 매수면 비싸게(+), 매도면 싸게(-) 체결되는 불리한 조건
            raw_price = self.data[ticker].loc[execution_time, 'Open']
            if np.isnan(raw_price) or raw_price <= 0:
                continue # 거래 정지 또는 상장 전
                
            execution_price = raw_price * (1 + config.slippage_rate) if target_qty > 0 else raw_price * (1 - config.slippage_rate)
            
            # 1.차 수량 소수점(Fractional) 제약 검증
            # 코인 또는 가상자산 티커(BTC, ETH)에 대해 소수점 매매 허용
            is_crypto = ticker.startswith("KRW-") or ticker in ['BTC', 'ETH']
            allowed_fractional = is_crypto
            if not allowed_fractional:
                # 주식/ETF는 정수(1주 단위) 단위로 내림(매수) 또는 올림(매도)
                # 매수(양수): 3.8주 -> 3주. 매도(음수): -3.8주 -> -3주
                target_qty = np.trunc(target_qty)
                if target_qty == 0:
                    continue # 1주도 못 사는 시그널은 무시
                    
            # 2차. 현금 및 자산 보유량(Short 금지) 검증
            trade_value = target_qty * execution_price
            commission_rate = config.crypto_commission_rate if is_crypto else config.stock_commission_rate
            commission = abs(trade_value) * commission_rate
            
            if target_qty > 0: # 매수
                total_cost = trade_value + commission
                if total_cost > self.status['cash']:
                    self.logger.debug(f"{execution_time} [{ticker}] 매수 현금 부족. 요구: {total_cost}, 잔고: {self.status['cash']}")
                    
                    # 영끌 매수 (살 수 있는 만큼만 다시 쪼개서 구매)
                    adjusted_qty = self.status['cash'] / (execution_price * (1 + commission_rate))
                    target_qty = adjusted_qty if allowed_fractional else np.trunc(adjusted_qty)
                    
                    if target_qty <= 0:
                        continue # 조정 후 1주도 안 되면 포기
                    
                    trade_value = target_qty * execution_price
                    commission = trade_value * commission_rate
                    total_cost = trade_value + commission

                # 체결 반영
                if total_cost > self.status['cash']:
                    # 최종 안전장치: 정말 소액 차이라면 소지 현금 전액 사용
                    total_cost = self.status['cash']
                    trade_value = total_cost / (1 + commission_rate)
                    commission = total_cost - trade_value
                    target_qty = trade_value / execution_price

                self.status['cash'] -= total_cost
                old_qty = self.status['holdings'][ticker]
                old_avg = self.status['avg_prices'][ticker]
                new_qty = old_qty + target_qty
                # 이동평균 단가 갱신
                self.status['avg_prices'][ticker] = ((old_qty * old_avg) + trade_value) / new_qty
                self.status['holdings'][ticker] = new_qty
                
                self.trades_log.append({
                    'Date': execution_time,
                    'Ticker': ticker,
                    'Action': 'BUY',
                    'Price': execution_price,
                    'Quantity': target_qty,
                    'Value': trade_value,
                    'Commission': commission
                })
            
            elif target_qty < 0: # 매도 
                sell_qty = abs(target_qty)
                current_hold = self.status['holdings'][ticker]
                
                # 없는 주식을 팔 수 없음 (공매도 금지)
                if sell_qty > current_hold:
                    sell_qty = current_hold
                    if sell_qty <= 0:
                        continue
                        
                trade_value = sell_qty * execution_price
                commission = trade_value * commission_rate
                net_proceeds = trade_value - commission
                
                # 체결 반영
                self.status['cash'] += net_proceeds
                self.status['holdings'][ticker] -= sell_qty
                
                self.trades_log.append({
                    'Date': execution_time,
                    'Ticker': ticker,
                    'Action': 'SELL',
                    'Price': execution_price,
                    'Quantity': sell_qty,
                    'Value': trade_value,
                    'Commission': commission
                })
                
                # 전량 매도시 단가 초기화
                if self.status['holdings'][ticker] < 1e-8:
                    self.status['holdings'][ticker] = 0.0
                    self.status['avg_prices'][ticker] = 0.0

    def _record_history(self, current_time: pd.Timestamp):
        """현재 시점의 포트폴리오 평가액 및 비중 기록"""
        eval_values = {}
        total_holdings_value = 0.0
        
        for ticker, qty in self.status['holdings'].items():
            if qty > 0:
                current_price = self.data[ticker].loc[current_time, 'Close']
                # NaN이면 전일 종가 등으로 이미 ffill 처리되어 있으므로 그대로 사용
                val = qty * current_price
            else:
                val = 0.0
                
            eval_values[f"{ticker}_val"] = val
            total_holdings_value += val
            
        total_portfolio_value = total_holdings_value + self.status['cash']
        
        rec = {
            'Date': current_time,
            'Cash': self.status['cash'],
            'Holdings_Value': total_holdings_value,
            'Total_Value': total_portfolio_value
        }
        rec.update(eval_values)
        self.history.append(rec)
