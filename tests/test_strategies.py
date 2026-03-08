import sys
import os
import pytest
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from strategies.value_averaging import ValueAveragingStrategy

@pytest.fixture
def sample_va_strategy():
    strategy = ValueAveragingStrategy(
        name="VA_TEST",
        ticker="SPY",
        initial_allocation=1_000_000,
        monthly_growth_rate=0.01,
        max_cap_rate=0.05,
        tolerance_band=0.02
    )
    return strategy

def test_va_initialization(sample_va_strategy):
    strategy = sample_va_strategy
    assert strategy.name == "VA_TEST"
    assert strategy.ticker == "SPY"
    assert strategy.monthly_growth_rate == 0.01

def test_va_generate_signals(sample_va_strategy):
    strategy = sample_va_strategy
    
    # 임의의 시계열 데이터 프레임 생성
    dates = pd.date_range("2020-01-01", "2020-03-31", freq='ME')
    df = pd.DataFrame({'Close': [100.0, 110.0, 95.0]}, index=dates)
    
    current_time = df.index[0]
    portfolio_status = {
        'cash': 500_000,
        'holdings': {'SPY': 0.0}
    }
    
    signals = strategy.generate_signals(current_time, df, portfolio_status)
    assert 'SPY' in signals
    
    # 목표 역산:
    # Month 1 Target = 1,000,000 * 1.01 = 1,010,000. Diff = 1,010,000. 
    # Max buy = 1,010,000 * 0.05 = 50,500.
    # Buy amount = min(1010000, 50500, 500_000) = 50,500.
    # Quantity = 50,500 / 100.0 = 505.0
    assert signals['SPY'] == 505.0
