import yfinance as yf
import pyupbit
import pandas as pd
import os
from typing import Dict
from config.settings import config, setup_logger
from datetime import datetime, timedelta

logger = setup_logger("api_fetcher")

def fetch_yfinance_hourly(ticker: str, days_back: int = 720) -> pd.DataFrame:
    """
    yfinance를 통해 특정 티커의 1시간봉(Hourly) 또는 일봉 데이터를 가져옵니다.
    참고: yfinance의 1시간봉(interval='1h')은 최대 730일까지만 무료 제공됩니다.
    """
    logger.info(f"Fetching {ticker} data from yfinance...")
    try:
        # yfinance의 1h 데이터 제한 기간 처리
        # - 1시간봉: 최대 729일(yfinance API 제한)
        # - 일봉: config.start_date 를 직접 시작점으로 사용 (장기 백테스트 기간 완전 확보)
        if config.use_hourly_data:
            start_date = datetime.now() - timedelta(days=min(days_back, 729))
        else:
            start_date = datetime.strptime(config.start_date, '%Y-%m-%d')
        
        df = yf.download(
            tickers=ticker,
            start=start_date.strftime('%Y-%m-%d'),
            interval='1h' if config.use_hourly_data else '1d',
            progress=False
        )
        if df.empty:
            logger.warning(f"No data fetched for {ticker}")
            return pd.DataFrame()
            
        # 다운로드 데이터 표준화 (불필요한 컬럼/멀티인덱스 정리)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
            
        df.index.name = 'Date'
        
        # 타임존 일관성 처리: yfinance는 종목에 따라 NY 타임 혹은 UTC 등 다양하게 반환함
        # 이미 tz-aware인 경우 바로 한국시간(KST)으로 변환하고, naive인 경우 UTC로 간주 후 변환
        if df.index.tz is None:
            df.index = df.index.tz_localize('UTC').tz_convert('Asia/Seoul')
        else:
            df.index = df.index.tz_convert('Asia/Seoul')
            
        # OOM(Out of Memory) 방지를 위해 데이터 타입을 float32로 하향 조정 반환
        return df[['Open', 'High', 'Low', 'Close', 'Volume']].astype('float32')
        
    except Exception as e:
        logger.error(f"Failed to fetch yfinance data for {ticker}: {e}")
        return pd.DataFrame()

def fetch_upbit_hourly(ticker: str, count: int = 800 * 24) -> pd.DataFrame:
    """
    pyupbit를 통해 코인(예: KRW-BTC)의 1시간봉 데이터를 가져옵니다.
    1시간 봉 데이터는 count를 늘려서 2년 이상의 장기 데이터를 확보할 수 있습니다 (800일 * 24).
    """
    logger.info(f"Fetching {ticker} data from pyupbit...")
    try:
        interval = "minute60" if config.use_hourly_data else "day"
        df = pyupbit.get_ohlcv(ticker, interval=interval, count=count)
        
        if df is None or df.empty:
            logger.warning(f"No data fetched for {ticker}")
            return pd.DataFrame()
            
        df.index.name = 'Date'
        # pyupbit는 기본적으로 로컬(KST) 시간으로 반환하나, 명시적으로 타임존 인지(aware) 객체로 생성
        if df.index.tz is None:
            df.index = df.index.tz_localize('Asia/Seoul')
            
        return df[['open', 'high', 'low', 'close', 'volume']].rename(
            columns={'open':'Open', 'high':'High', 'low':'Low', 'close':'Close', 'volume':'Volume'}
        ).astype('float32')
        
    except Exception as e:
        logger.error(f"Failed to fetch pyupbit data for {ticker}: {e}")
        return pd.DataFrame()
