import os
import sys
import pandas as pd
from typing import Dict, Any

# 루트 디렉토리를 PATH에 추가하여 src 모듈 접근 허용
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from config.settings import config, setup_logger
from data_io.csv_loader import DataLoader
from strategies.value_averaging import ValueAveragingStrategy, VolatilityTargetingInversePyramid
from backtest.engine import BacktestEngine
from visualization.plot_utils import plot_asset_allocation, generate_tear_sheet, generate_markdown_report

logger = setup_logger("main")

def run_pipeline():
    # 설정된 strat_date(2019-01-01 등) 사용. 
    logger.info("Starting Dynamic Portfolio Backtest Pipeline...")
    
    # 1. 포트폴리오 자산 유니버스 (티커) 정의
    # (한국투자/키움 등 실 데이터 연동 시 이 구성을 변경, 코인은 KRW- prefix 필수)
    portfolio_tickers = {
        'NASDAQ100': 'QQQ',     # NASDAQ 100 ETF (Core, 25%)
        'KOSPI': '278530.KS',   # KODEX 200TR (Satellite 1, 15%)
        'VEA': 'VEA',           # 선진국 글로벌 ETF (Satellite 2, 10%)
        'TLT': 'TLT',           # 미국 장기채 ETF (Hedge, 15%)
        'SHV': 'SHV',           # 단기채 ETF (안전자산 충족용, 10%)
        'GLD': 'GLD'            # 금 ETF (Hedge, 15%)
    }

    # 2. 데이터 수집 및 동기화된 타임라인 로드
    loader = DataLoader(raw_dir='data/raw/')
    synced_data = loader.get_synced_portfolio_data(portfolio_tickers)
    
    if not synced_data:
        logger.error("데이터 로드 실패. 파이프라인을 종료합니다.")
        return

    # 3. 전략 객체 초기화
    logger.info("Initializing trading strategies...")
    strategies = []
    
    # 3.1. NASDAQ 100 가치평균법 (Core 30%)
    va_qqq = ValueAveragingStrategy(
        name="VA_NASDAQ100", 
        ticker='NASDAQ100', 
        initial_allocation=config.initial_investment * config.weight_nasdaq100,
        monthly_growth_rate=config.va_growth_rate_nasdaq100, 
        max_cap_rate=config.va_max_purchase_cap,
        rolling_window_years=3,
        update_frequency_months=6
    )
    va_qqq.precalculate_targets(synced_data['NASDAQ100'])
    strategies.append(va_qqq)

    # 3.2. KOSPI 가치평균법 (Satellite 1 20%)
    # QQQ, GLD, TLT는 밴드 없이 기계적 매도 / KOSPI는 랠리 허용 밴드(5%) 적용
    va_kospi = ValueAveragingStrategy(
        name="VA_KOSPI", 
        ticker='KOSPI', 
        initial_allocation=config.initial_investment * config.weight_kospi,
        monthly_growth_rate=config.va_growth_rate_kospi, 
        max_cap_rate=config.va_max_purchase_cap,
        tolerance_band=config.tolerance_band_kospi,
        rolling_window_years=1,
        update_frequency_months=6
    )
    va_kospi.precalculate_targets(synced_data['KOSPI'])
    strategies.append(va_kospi)

    # 3.3. 금 ETF 가치평균법 (Hedge 15%)
    va_gld = ValueAveragingStrategy(
        name="VA_GLD", 
        ticker='GLD', 
        initial_allocation=config.initial_investment * config.weight_gld,
        monthly_growth_rate=config.va_growth_rate_gld, 
        max_cap_rate=config.va_max_purchase_cap,
        rolling_window_years=1,
        update_frequency_months=6
    )
    va_gld.precalculate_targets(synced_data['GLD'])
    strategies.append(va_gld)
    
    # 3.4. 단기채 ETF 가치평균법 (Safe Asset 10%)
    va_shv = ValueAveragingStrategy(
        name="VA_SHV", 
        ticker='SHV', 
        initial_allocation=config.initial_investment * config.weight_shv,
        monthly_growth_rate=config.va_growth_rate_shv, 
        max_cap_rate=config.va_max_purchase_cap,
        rolling_window_years=3,
        update_frequency_months=6
    )
    va_shv.precalculate_targets(synced_data['SHV'])
    strategies.append(va_shv)
    
    # 3.5. 선진국 MSCI ETF 가치평균법 (Global 10%)
    va_vea = ValueAveragingStrategy(
        name="VA_VEA", 
        ticker='VEA', 
        initial_allocation=config.initial_investment * config.weight_vea,
        monthly_growth_rate=config.va_growth_rate_vea, 
        max_cap_rate=config.va_max_purchase_cap,
        rolling_window_years=3,
        update_frequency_months=6
    )
    va_vea.precalculate_targets(synced_data['VEA'])
    strategies.append(va_vea)
    
    # 3.6. 장기국채 ETF 가치평균법 (Hedge 15%)
    va_tlt = ValueAveragingStrategy(
        name="VA_TLT", 
        ticker='TLT', 
        initial_allocation=config.initial_investment * config.weight_tlt,
        monthly_growth_rate=config.va_growth_rate_tlt, 
        max_cap_rate=config.va_max_purchase_cap,
        rolling_window_years=3,
        update_frequency_months=6
    )
    va_tlt.precalculate_targets(synced_data['TLT'])
    strategies.append(va_tlt)

    # 4. 백테스트 엔진 구동
    engine = BacktestEngine(synced_data, strategies, logger)
    result_history, trades_df = engine.run()
    
    if result_history.empty:
        logger.error("Simulation produced no history data.")
        return
        
    # 5. 성과 리포트 출력 및 차트 저장
    reports_dir = 'reports'
    os.makedirs(reports_dir, exist_ok=True)
    
    timestamp = pd.Timestamp.now().strftime("%Y%m%d_%H%M")
    
    # 티어시트 텍스트
    generate_tear_sheet(result_history, trades_df, save_path=f"{reports_dir}/tear_sheet_{timestamp}.txt")
    
    # 시각화 이미지 (자산 비중만 표기)
    plot_asset_allocation(result_history, save_path=f"{reports_dir}/allocation_{timestamp}.png")
    
    # 추가 데이터 저장
    if trades_df is not None and not trades_df.empty:
        trades_df.to_csv(f"{reports_dir}/trades_history_{timestamp}.csv")
        
    # 🌟 추가: Markdown 종합 리포트 생성
    generate_markdown_report(result_history, trades_df, save_path=f"{reports_dir}/weekly_trade_plan_{timestamp}.md", timestamp=timestamp)
    logger.info(f"주간 운용 계획서(MD) 생성이 완료되었습니다.")
    
    # 히스토리 CSV 덤프
    result_history.to_csv(f"{reports_dir}/history_{timestamp}.csv")
    
    logger.info(f"파이프라인 종료. 분석 결과가 '{reports_dir}/' 디렉토리에 저장되었습니다.")

if __name__ == "__main__":
    run_pipeline()
