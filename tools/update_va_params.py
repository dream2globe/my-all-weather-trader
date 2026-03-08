import os
import sys
import pandas as pd
import numpy as np

# 프로젝트 루트 경로 추가
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

from data_io.csv_loader import DataLoader
from features.indicators import calculate_performance_metrics

def evaluate_window_sizes(df: pd.DataFrame, ticker_name: str, test_windows: list = [1, 3, 5, 7]):
    """
    각 롤링 윈도우(Look-back Period) 크기별로 최근 데이터를 슬라이싱하여
    연환산 수익률(CAGR)과 변동성(Volatility)을 측정, 가장 우수한 윈도우를 추천합니다.
    """
    current_date = df.index[-1]
    print(f"\n[{ticker_name}] 분석 시작 (최근 날짜: {current_date.strftime('%Y-%m-%d')})")
    
    results = []
    
    for years in test_windows:
        start_date = current_date - pd.DateOffset(years=years)
        window_df = df[df.index >= start_date].copy()
        
        if len(window_df) < 50: # (약 2달치 이하 데이터가 없으면 무시)
            print(f" - {years}년 구간: 데이터 부족 (Row: {len(window_df)})")
            continue
            
        # 단순히 매수 후 보유(Buy & Hold) 했을 때의 지표
        first_price = float(window_df['Close'].iloc[0])
        last_price = float(window_df['Close'].iloc[-1])
        
        # 일봉(Daily) 또는 시간봉 여부에 상관없이 (마지막 날 - 첫 날)의 실제 연도 차이로 CAGR 계산
        delta_years = (window_df.index[-1] - window_df.index[0]).days / 365.25
        
        if delta_years <= 0 or first_price <= 0:
            continue
            
        cagr = (last_price / first_price) ** (1 / delta_years) - 1
        window_df['Return'] = window_df['Close'].pct_change()
        # 시간봉 스케일 가이드: (보수적으로 일봉 변환 후 측정이라 가정)
        volatility = window_df['Return'].std() * np.sqrt(252 * (1 if '00:00:00' in str(window_df.index[0]) else 8))
        
        # 위험 대비 수익률 (위험보상비율)
        score = (cagr / volatility) if volatility > 0 else 0
        
        results.append({
            'Window_Years': years,
            'CAGR': cagr,
            'Volatility': volatility,
            'Score': score
        })
        
    if not results:
        print(f"{ticker_name}: 평가 가능한 윈도우 구간이 없습니다.")
        return None
        
    results_df = pd.DataFrame(results)
    print(results_df.to_string(index=False, float_format="%.4f"))
    
    # 🌟 최적 윈도우 선정 로직:
    # 무조건 수익률(CAGR)이 높다고 고르는 것이 아니라 수익성과 변동성을 모두 따진 Score 기준
    best_idx = results_df['Score'].idxmax()
    best_row = results_df.loc[best_idx]
    
    print(f"✅ 최적 윈도우 사이즈: {int(best_row['Window_Years'])}년 " +
          f"(CAGR: {best_row['CAGR']*100:.2f}%, Volatility: {best_row['Volatility']*100:.2f}%)")
    
    # 해당 윈도우의 연 환산치(CAGR)를 바탕으로 월 복리 목표치(VGP) 역산
    monthly_target = (1 + best_row['CAGR']) ** (1/12) - 1
    # 만약 손실(-CAGR) 구간이라면 보수적으로 +0.1%로 방어 세팅
    if monthly_target <= 0:
        monthly_target = 0.001
        
    print(f"➡️ 추천 가치평균법(VA) 월 목표 성장률: {monthly_target*100:.3f}%\n")
    
    return {
        'best_window_years': int(best_row['Window_Years']),
        'suggested_monthly_rate': monthly_target
    }

def main():
    print("="*50)
    print(" VA 파라미터 롤링 윈도우 사이즈 자동 최적화 봇 ")
    print("="*50)
    
    # 🌟 엔진용 settings.start_date (예: 2026-01-05) 제약에 걸리지 않도록
    # 봇이 스스로 start_date를 아주 먼 과거로 임시 할당하여 전체 데이터를 확보합니다.
    from config.settings import config
    config.start_date = "2015-01-01"
    
    loader = DataLoader()
    tickers_to_eval = {
        'SP500': 'SPY',
        'KOSPI': '229200.KS',
        'GLD': 'GLD',
        'SHV': 'SHV'
    }
    
    portfolio_data = loader.get_synced_portfolio_data(tickers_to_eval)
    
    if not portfolio_data:
        print("데이터 로딩에 실패했습니다.")
        return
        
    final_suggestions = {}
    
    for name, df in portfolio_data.items():
        # NaN 제거 (결측치 데이터 컷오프)
        clean_df = df.dropna(subset=['Close'])
        suggestion = evaluate_window_sizes(clean_df, name, test_windows=[1, 3, 5, 7])
        if suggestion:
            final_suggestions[name] = suggestion
            
    print("="*50)
    print(" 최적화 완료 요약표 ")
    print(" (이 결과값을 settings.py 에 업데이트 하십시오) ")
    print("="*50)
    for name, data in final_suggestions.items():
        print(f" - {name} ({data['best_window_years']}년 기준) : {data['suggested_monthly_rate']:.5f}")

if __name__ == "__main__":
    main()
