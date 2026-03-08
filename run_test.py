import pandas as pd
import numpy as np
import logging
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))
from config.settings import config
from backtest.engine import BacktestEngine
from strategies.base_strategy import BaseStrategy

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("test")

class DummyStrategy(BaseStrategy):
    def __init__(self, name, ticker, signal_values):
        super().__init__(name)
        self.ticker = ticker
        self.signal_values = signal_values
        self.call_count = 0
        
    def generate_signals(self, current_time, data, portfolio_status):
        if self.call_count < len(self.signal_values):
            val = self.signal_values[self.call_count]
        else:
            val = 0.0
        self.call_count += 1
        return {self.ticker: val}

# Test Data Mock
dates = pd.date_range('2023-01-01', periods=5, freq='D')
df = pd.DataFrame({
    'Open': [100.0, 110.0, 120.0, 90.0, 100.0],
    'High': [105.0, 115.0, 125.0, 95.0, 105.0],
    'Low':  [95.0, 105.0, 115.0, 85.0, 95.0],
    'Close':[110.0, 120.0, 90.0, 100.0, 110.0],
    'Volume':[1000]*5
}, index=dates)
df.index.name = 'Date'
mock_data = {'DUMMY': df}

def test_engine():
    print("=== Starting Engine Core Test ===")
    
    # 전략: T=0(종가 110)에서 10주 매수 -> T=1 시가(110)에 10주 매수 체결
    #       T=2(종가 90)에서 -5주 매도 -> T=3 시가(90)에 5주 매도 체결
    strategy = DummyStrategy("Test", "DUMMY", [10.0, 0.0, -5.0, 0.0, 0.0])
    
    engine = BacktestEngine(mock_data, [strategy], logger)
    res = engine.run()
    
    print("\n=== Test Results ===")
    print("History DataFrame Shape:", res.shape)
    print("Final Holdings:", engine.status['holdings']['DUMMY'])
    print("Final Cash:", engine.status['cash'])
    
    print("\nResult DataFrame:")
    print(res.to_string())
    
    if engine.status['holdings']['DUMMY'] != 5.0:
        print("FAIL: Final holdings should be 5.0")
        sys.exit(1)
        
    if res.shape[0] != 5:
        print("FAIL: Should contain 5 days of history")
        sys.exit(1)
        
    print("SUCCESS: Engine core logic passed self-test.")

if __name__ == '__main__':
    test_engine()
