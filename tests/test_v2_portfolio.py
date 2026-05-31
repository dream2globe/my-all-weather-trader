import sys
import os
import pytest
import pandas as pd

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from config.settings import BacktestSettings
from strategies.value_averaging import ValueAveragingStrategy

def test_v2_2_weights():
    # v2.2 포트폴리오 비중 검증 테스트
    config = BacktestSettings()
    assert config.weight_nasdaq100 == 0.25, "NASDAQ100 비중은 25%여야 합니다."
    assert config.weight_kospi == 0.15, "KOSPI 비중은 15%여야 합니다."
    assert config.weight_vea == 0.10, "VEA 비중은 10%여야 합니다."
    assert config.weight_tlt == 0.15, "TLT 비중은 15%여야 합니다."
    assert config.weight_gld == 0.15, "GLD 비중은 15%여야 합니다."
    assert config.weight_shv == 0.10, "SHV 비중은 10%여야 합니다."
    assert config.cash_buffer_weight == 0.10, "현금 버퍼 비중은 10%여야 합니다."
    
    total_weights = (config.weight_nasdaq100 + config.weight_kospi + 
                     config.weight_vea + config.weight_tlt + 
                     config.weight_gld + config.weight_shv + 
                     config.cash_buffer_weight)
    
    # 총합이 정확히 100%인지 확인
    assert abs(total_weights - 1.0) < 1e-6, "비중의 총합산은 100%여야 합니다."

def test_va_weekly_evaluation():
    # 주단위(Weekly) 모니터링 시 가치평균법이 정확히 목표궤도를 유지하는지 검증
    # 조건: 나스닥 자산, 초기 배분 7500만원 (3억의 25%), 월간 타겟 0.9%
    strategy = ValueAveragingStrategy(
        name="VA_NASDAQ_TEST",
        ticker="QQQ",
        initial_allocation=75_000_000.0,
        monthly_growth_rate=0.009,
        max_cap_rate=0.05
    )
    
    # 일주일 간격의 주가
    dates = [
        pd.Timestamp("2026-04-06"), # Week 1
        pd.Timestamp("2026-04-13"), # Week 2
        pd.Timestamp("2026-04-20")  # Week 3
    ]
    
    df = pd.DataFrame({'Close': [100.0, 90.0, 110.0]}, index=dates)
    portfolio_status = {'cash': 30_000_000, 'holdings': {'QQQ': 0.0}}
    
    # Week 1 투입 전 목표 금액 = 75,000,000 * 1.009 (첫 달 업데이트 시)
    signals_w1 = strategy.generate_signals(dates[0], df, portfolio_status)
    
    # 첫 달 목표: 75,000,000 * 1.009 = 75,675,000
    # 주가 100.0, 보유량 0.0 -> Gap = 75,675,000
    # 자본 Cap: 75,675,000 * 0.05 = 3,783,750 원 제한됨
    # 매수 가능 주식 수 = 37,837.5 주
    assert signals_w1['QQQ'] == pytest.approx(37837.5)
    
    # Week 1 체결 반영
    portfolio_status['holdings']['QQQ'] = 37837.5
    
    # Week 2 주가 하락 시 (100 -> 90) 추가 매수 지시량 파악
    # 현 평가액: 37837.5 * 90 = 3,405,375
    # 여전히 월 목표 75,675,000 대비 현저히 부족하므로 Max Cap 한도 내에서 풀 매수 지시해야 함.
    # 주가가 90이므로 3,783,750 / 90.0 = 42041.666...
    signals_w2 = strategy.generate_signals(dates[1], df, portfolio_status)
    assert signals_w2['QQQ'] == pytest.approx(3783750 / 90.0)

def test_tolerance_band_kospi():
    """KOSPI 상단 오차 한도 5% 적용 시, 주단위 점검 시에도 매도 유예(관망)가 되는지 검증"""
    strategy = ValueAveragingStrategy(
        name="VA_KOSPI_TEST",
        ticker="KOSPI",
        initial_allocation=45_000_000, # 15% of 3억
        monthly_growth_rate=0.003,
        max_cap_rate=0.05,
        tolerance_band=0.05
    )
    
    dates = [pd.Timestamp("2026-04-06")]
    
    # 가치평균법 목표금액 갱신: 45,000,000 * 1.003 = 45,135,000
    # 보유량 임의 조작: 목표치 대비 딱 3% 치솟은 상황이라 가정 (45,135,000 * 1.03)
    current_val_at_100 = 45_135_000 * 1.03 
    df = pd.DataFrame({'Close': [100.0]}, index=dates)
    portfolio_status = {'cash': 10_000, 'holdings': {'KOSPI': current_val_at_100 / 100.0}}
    
    signals = strategy.generate_signals(dates[0], df, portfolio_status)
    
    # 타겟을 오버했지만 +5% 톨러런스 구간 이내라 매도 신호가 안 나가고 관망(Hold: 0.0 혹은 생략)해야 함
    if 'KOSPI' in signals:
        assert signals['KOSPI'] == 0.0, "톨러런스 밴드 이내에서는 부분 익절 지시가 나오면 안 됩니다."
