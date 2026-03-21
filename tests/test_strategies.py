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

def test_va_with_monthly_injection():
    # 90M 초기 투자, 23.33M 월간 투입 가정
    strategy = ValueAveragingStrategy(
        name="VA_MONTHLY",
        ticker="KOSPI",
        initial_allocation=27_000_000,
        monthly_growth_rate=0.003,
        max_cap_rate=0.05,
        monthly_injection=7_000_000 # KOSPI 비중 30% 기준 (23.33M * 0.3)
    )
    
    # Month 1 Start
    dates = [pd.Timestamp("2020-01-06"), pd.Timestamp("2020-01-13"), pd.Timestamp("2020-02-03")]
    df = pd.DataFrame({'Close': [100.0, 100.0, 100.0]}, index=dates)
    
    portfolio_status = {'cash': 100_000_000, 'holdings': {'KOSPI': 0.0}}
    
    # Week 1 (Jan 6) - Target becomes (Initial * 1.003) + Injection = (27M * 1.003) + 7M = 34,081,000
    signals = strategy.generate_signals(dates[0], df, portfolio_status)
    # Max Cap = 34,081,000 * 0.05 = 1,704,050
    # Buy = 1,704,050 / 100 = 17040.5
    assert signals['KOSPI'] == 17040.5
    
    # Update portfolio (simulating buy)
    portfolio_status['holdings']['KOSPI'] = 17040.5
    
    # Week 2 (Jan 13) - Still same month, but target calculated once per month change. 
    # Current implementation updates target if month != last_month.
    # On first call, last_month is None, so it updates to Month 1.
    signals = strategy.generate_signals(dates[1], df, portfolio_status)
    # Diff = 34,081,000 - (17040.5 * 100) = 34,081,000 - 1,704,050 = 32,376,950
    # Max Cap approx same. 
    assert signals['KOSPI'] > 0
    
    # Week 3 (Feb 3) - Monthly change!
    # Target = (34,081,000 * 1.003) + 7,000,000 = 34,183,243 + 7,000_000 = 41,183,243
    signals = strategy.generate_signals(dates[2], df, portfolio_status)
    assert strategy.current_target_value > 41_000_000

