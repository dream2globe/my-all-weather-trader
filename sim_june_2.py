import math

planned_capital = 136666666 + 23333333

weights = {
    'NASDAQ100': 0.25,
    'KOSPI': 0.15,
    'VEA': 0.10,
    'COPPER': 0.10,
    'TLT': 0.05,
    'GLD': 0.15,
    'SHV': 0.10
}

growth_rates = {
    'NASDAQ100': 0.009,
    'KOSPI': 0.003,
    'VEA': 0.004,
    'COPPER': 0.004,
    'TLT': 0.0035,
    'GLD': 0.004,
    'SHV': 0.0005
}

current_values = {
    'NASDAQ100': 34890000,
    'KOSPI': 27501500,
    'VEA': 12264000,
    'COPPER': 8290000,
    'TLT': 0,
    'GLD': 19821750,
    'SHV': 23885500
}

# elapsed_months is 2 for June 1st (84 days // 30 = 2)
elapsed_months = 2

tolerance_band = 0.05
va_max_purchase_cap = 0.05

print(f"Planned Capital: {planned_capital}")
for asset, weight in weights.items():
    gr = growth_rates[asset]
    cv = current_values[asset]
    
    base_allocation = planned_capital * weight
    target_value = base_allocation * ((1 + gr) ** elapsed_months)
    diff = target_value - cv
    
    base_action_amount = 0.0
    
    if diff > 0:
        dynamic_max_buy = target_value * va_max_purchase_cap
        base_action_amount = min(diff, dynamic_max_buy)
    elif diff < 0:
        exceed_ratio = abs(diff) / target_value
        if exceed_ratio > tolerance_band:
            pure_exceed_value = abs(diff) - (target_value * tolerance_band)
            base_action_amount = -(pure_exceed_value * 0.5)
        else:
            base_action_amount = 0.0

    print(f"{asset}: Target={target_value:.0f}, Current={cv:.0f}, Gap={diff:.0f}, Action={base_action_amount:.0f}")
