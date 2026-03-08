import pandas as pd
import itertools
from typing import Dict, List, Callable, Any
from backtest.engine import BacktestEngine
from features.indicators import calculate_performance_metrics
from config.settings import setup_logger

logger = setup_logger("optimizer")

class ParameterOptimizer:
    """
    그리드 서치 기법을 이용해 KOSPI 익절 기준치나 암호화폐 그리드 간격 등
    모호한 파라미터 조합의 전수 조사를 수행하여 최적의 파라미터를 발굴.
    """
    def __init__(self, data: Dict[str, pd.DataFrame]):
        self.data = data
        self.best_result = None
        self.best_params = None
        
    def run_grid_search(self, strategy_builder: Callable, param_grid: Dict[str, List[Any]]) -> pd.DataFrame:
        """
        단일 시뮬레이션을 생성하는 builder 함수와, 테스트해 볼 파라미터 딕셔너리를 입력받음.
        
        Args:
            strategy_builder: (params_dict) -> List[BaseStrategy] 를 반환하는 팩토리 함수
            param_grid: {'kospi_profit': [0.05, 0.10, 0.15], 'mdd_level': [-0.15, -0.20]}
        Returns:
            모든 조합의 성과 평가 지표를 담은 요약 DataFrame
        """
        keys, values = zip(*param_grid.items())
        combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]
        
        logger.info(f"Starting Grid Search with {len(combinations)} parameter combinations...")
        results = []
        
        for i, params in enumerate(combinations):
            logger.info(f"Test {i+1}/{len(combinations)} : {params}")
            
            # 파라미터에 맞는 전략 인스턴스 배열 생성
            strategies = strategy_builder(params)
            
            engine = BacktestEngine(self.data, strategies, logger)
            try:
                history = engine.run()
                metrics = calculate_performance_metrics(history)
                
                # 조합 파라미터와 결과 합성
                res = {**params, **metrics}
                results.append(res)
                
                # 최적 여부 판단(예: CAGR 기준)
                if self.best_result is None or metrics.get('CAGR', -99) > self.best_result.get('CAGR', -99):
                    self.best_result = metrics
                    self.best_params = params
                    
            except Exception as e:
                logger.error(f"Error evaluating params {params}: {e}")
                
        logger.info(f"Search Finished! Best CAGR: {self.best_result.get('CAGR')} with Params: {self.best_params}")
        
        return pd.DataFrame(results)
