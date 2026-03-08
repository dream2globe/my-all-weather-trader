import pandas as pd
import numpy as np
from config.settings import config, setup_logger

logger = setup_logger("indicators")

def calculate_rolling_mdd(df: pd.DataFrame, window: int = 60 * 24) -> pd.Series:
    """
    최근 window 일수(또는 시간) 동안의 국소 고점(Local High) 대비 현재가의 하락률(MDD)을 계산.
    Args:
        df: 'Close' 등 기준이 될 가격 컬럼을 갖는 시계열 데이터프레임
        window: window 사이즈(예: 1시간 봉 기준 60일이면 60*24). 일봉이면 단순히 60
    """
    rolling_max = df['Close'].rolling(window=window, min_periods=1).max()
    drawdown = df['Close'] / rolling_max - 1.0
    return drawdown

def calculate_moving_average(df: pd.DataFrame, window: int = 120 * 24) -> pd.Series:
    """N일(기간) 이동평균선(SMA) 계산"""
    return df['Close'].rolling(window=window, min_periods=window).mean()

def calculate_va_target(df: pd.DataFrame, monthly_growth_rate: float, initial_investment: float) -> pd.Series:
    """
    복리 성장률 기반의 가치평균 목표 평가액 성장 곡선(Target Value Path) 계산.
    매월 말(또는 환산된 시간축 상 30일(720시간)마다) 목표치가 step-up 하는 형태로 계산.
    """
    if df.empty:
        return pd.Series(dtype=float)

    # 시간에 상관없이 시작일(row 0)부터 지난 '개월 수(30일 환산)' 계산.
    # 인덱스가 시계열일 경우 (현재일 - 시작일).days // 30 활용
    start_date = df.index[0]
    elapsed_months = (df.index - start_date).days // 30
    
    # 목표치 V_t = V_0 * (1 + r)^t
    target_values = initial_investment * ((1 + monthly_growth_rate) ** elapsed_months)
    return pd.Series(target_values, index=df.index, name='VA_Target')

def calculate_performance_metrics(history: pd.DataFrame) -> dict[str, float]:
    """
    Engine에서 출력된 Portfolio History를 바탕으로 백테스트 종합 성과를 계산.
    Args:
        history: ['Total_Value', 'Daily_Returns', 'Cumulative_Returns'] 등의 컬럼 포함
    """
    if history.empty or 'Total_Value' not in history.columns:
        return {}

    total_value = history['Total_Value']
    returns = total_value.pct_change().dropna()
    start_val = total_value.iloc[0]
    end_val = total_value.iloc[-1]
    
    # 1. 누적 수익률(Cumulative Return)
    cum_ret = (end_val / start_val) - 1.0
    
    # 2. 거래 기간 (연 단위 환산)
    days = (history.index[-1] - history.index[0]).days
    if days == 0:
        days = 1 # 분모가 0이 되는 것을 방지
    years = days / 365.25
    
    # 3. CAGR (복리 연수익률)
    cagr = (end_val / start_val) ** (1 / years) - 1.0 if years > 0 else 0
    
    # 4. 연환산 변동성 및 Sharpe Ratio (무위험 수익률 0% 가정)
    # 데이터 주기에 따라 연환산 인자 적용(1년 = 252 거래일 * 24시간 = 6048 h)
    # 코인 등 365일 연중무휴인 경우 365, 주식 252 섞임 -> 마스터 인덱스 빈도(약 1시간간격) 수 기반 산출
    obs_per_year = len(returns) / years if years > 0 else 252  
    
    volatility = returns.std() * np.sqrt(obs_per_year)
    sharpe = (cagr / volatility) if volatility > 0 else 0
    
    # 5. 최대 낙폭 (Max MDD)
    rolling_max = total_value.expanding().max()
    drawdowns = total_value / rolling_max - 1.0
    max_mdd = drawdowns.min()

    # 6. Sortino Ratio (하방 변동성만 고려)
    downside_returns = returns[returns < 0]
    downside_vol = downside_returns.std() * np.sqrt(obs_per_year)
    sortino = (cagr / downside_vol) if downside_vol > 0 else 0

    return {
        "Total Return": cum_ret,
        "CAGR": cagr,
        "Max MDD": max_mdd,
        "Sharpe Ratio": sharpe,
        "Sortino Ratio": sortino,
        "Volatility (Ann.)": volatility
    }

def calculate_atr(df: pd.DataFrame, window: int = 14) -> pd.Series:
    """
    고가, 저가, 종가를 바탕으로 Average True Range(ATR)를 계산하여 
    현재 종가 대비 일일 변동성 비율(ATR / Close)을 구합니다.
    """
    if len(df) < 2:
        return pd.Series(0.0, index=df.index, name='ATR_Ratio')
        
    high = df['High']
    low = df['Low']
    close_prev = df['Close'].shift(1)
    
    tr1 = high - low
    tr2 = (high - close_prev).abs()
    tr3 = (low - close_prev).abs()
    
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.ewm(span=window, adjust=False).mean()
    
    atr_ratio = atr / df['Close']
    return atr_ratio
