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
from visualization.plot_utils import plot_portfolio_growth, plot_drawdown, plot_asset_allocation, generate_tear_sheet, plot_trading_signals, generate_markdown_report

logger = setup_logger("main")

def run_pipeline():
    config.start_date = "2024-01-01"  # 비트코인/이더리움 실전 투자 시점인 2024년으로 시작일 조정
    logger.info("Starting Dynamic Portfolio Backtest Pipeline...")
    
    # 1. 포트폴리오 자산 유니버스 (티커) 정의
    # (한국투자/키움 등 실 데이터 연동 시 이 구성을 변경, 코인은 KRW- prefix 필수)
    portfolio_tickers = {
        'SP500': 'SPY',         # S&P 500 ETF (Core, 30%)
        'KOSPI': '229200.KS',   # KODEX 200 (Satellite 1, 15%)
        'GLD': 'GLD',           # 금 ETF (Hedge, 15%)
        'SHV': 'SHV',           # 단기채 ETF (안전자산 충족용, 15%)
        'BTC': 'KRW-BTC',       # 비트코인 (Satellite 2, 5%)
        'ETH': 'KRW-ETH'        # 이더리움 (Satellite 2, 5%)
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
    
    # 3.1. S&P500 가치평균법 (Core 30%)
    va_spy = ValueAveragingStrategy(
        name="VA_SP500", 
        ticker='SP500', 
        initial_allocation=config.initial_investment * config.weight_sp500,
        monthly_growth_rate=config.va_growth_rate_sp500, 
        max_cap_rate=config.va_max_purchase_cap,
        rolling_window_years=3,
        update_frequency_months=6
    )
    va_spy.precalculate_targets(synced_data['SP500'])
    strategies.append(va_spy)

    # 3.2. KOSPI 가치평균법 (Satellite 1 20%)
    # SPY, GLD, TLT는 밴드 없이 기계적 매도 / KOSPI는 랠리 허용 밴드(5%) 적용
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
    
    # 3.4. 국채 ETF 가치평균법 (Safe Asset 15%)
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
    
    # 3.5. BTC 변동성 타겟팅 역피라미드 (비활성)
    # vt_btc = VolatilityTargetingInversePyramid(
    #     name="VT_BTC",
    #     ticker='BTC',
    #     mdd_levels=[config.mdd_trigger_level_1, config.mdd_trigger_level_2, -0.40],
    #     invest_ratios=[0.0167, 0.0167, 0.0166],
    #     vol_target=config.btc_volatility_target
    # )
    # strategies.append(vt_btc)
    
    # 3.6. ETH 변동성 타겟팅 역피라미드 (비활성)
    # vt_eth = VolatilityTargetingInversePyramid(
    #     name="VT_ETH",
    #     ticker='ETH',
    #     mdd_levels=[config.mdd_trigger_level_1, config.mdd_trigger_level_2, -0.40],
    #     invest_ratios=[0.0167, 0.0167, 0.0166],
    #     vol_target=config.eth_volatility_target
    # )
    # strategies.append(vt_eth)

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
    
    # 시각화 이미지
    plot_portfolio_growth(result_history, save_path=f"{reports_dir}/growth_{timestamp}.png")
    plot_drawdown(result_history, save_path=f"{reports_dir}/mdd_{timestamp}.png")
    plot_asset_allocation(result_history, save_path=f"{reports_dir}/allocation_{timestamp}.png")
    
    # 🌟 추가: 상세 거래 타점 Scatter Plot & CSV 저장
    if trades_df is not None and not trades_df.empty:
        plot_trading_signals(synced_data, trades_df, save_path=f"{reports_dir}/trading_signals_{timestamp}.png")
        trades_df.to_csv(f"{reports_dir}/trades_history_{timestamp}.csv")
        logger.info(f"거래 타점 플롯 생성이 완료되었습니다.")
        
    # 🌟 추가: Markdown 종합 리포트 생성
    generate_markdown_report(result_history, trades_df, save_path=f"{reports_dir}/weekly_trade_plan_{timestamp}.md", timestamp=timestamp)
    logger.info(f"주간 운용 계획서(MD) 생성이 완료되었습니다.")
    
    # 히스토리 CSV 덤프
    result_history.to_csv(f"{reports_dir}/history_{timestamp}.csv")
    
    logger.info(f"파이프라인 종료. 분석 결과가 '{reports_dir}/' 디렉토리에 저장되었습니다.")

if __name__ == "__main__":
    run_pipeline()
