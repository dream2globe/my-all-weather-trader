import sys
import os
import pytest
import pandas as pd
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from backtest.engine import BacktestEngine
from strategies.base_strategy import BaseStrategy
from config.settings import config

class DummyStrategy(BaseStrategy):
    def __init__(self, name="Dummy"):
        super().__init__(name)
        self.ticker = 'SPY'
        
    def generate_signals(self, current_time, data, portfolio_status):
        # 매 단계마다 무조건 SPY 1주를 산다고 가정
        return {'SPY': 1.0}
        
def test_engine_run():
    # 5일간 매일 상승장 가정
    dates = pd.date_range("2020-01-01", "2020-01-05")
    df_spy = pd.DataFrame({'Open': [100, 101, 102, 103, 104],
                           'High': [100, 101, 102, 103, 104],
                           'Low': [100, 101, 102, 103, 104],
                           'Close': [100, 101, 102, 103, 104],
                           'Volume': [10, 10, 10, 10, 10]}, index=dates)
    
    data = {'SPY': df_spy}
    strategy = DummyStrategy()
    logger = logging.getLogger("test_engine")
    
    # 엔진 컨피그 모의 설정
    config.initial_investment = 10000
    config.slippage_rate = 0.0
    config.stock_commission_rate = 0.0
    
    engine = BacktestEngine(data, [strategy], logger)
    result_df, trades_df = engine.run()
    
    assert not result_df.empty
    assert len(result_df) == 5
    
    # 첫째 날은 시그널만 '예약'되고 체결되지 않으며 둘째 날 시가(Open)에 1주 매수
    # T=2(두번째날) 체결 -> 101원에 매수 (현금: 10000 - 101 = 9899)
    # T=5까지 계속 매수 -> 거래 기록이 4번 발생
    assert not trades_df.empty
    assert len(trades_df) == 4
    
    # 마지막 날 보유 주식 수는 4개여야 함
    assert engine.status['holdings']['SPY'] == 4.0
