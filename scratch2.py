import csv

real_prices = {
    '367380.KS': 33375.0,
    '278530.KS': 42310.0,
    '251350.KS': 40880.0,
    '160580.KS': 16580.0,
    '453850.KS': 7330.0,
    '411060.KS': 30495.0,
    '0046A0.KS': 10385.0
}

holdings = {}
invested = {}

with open('data/actual_trades.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        ticker = row['Ticker']
        action = row['Action']
        price = float(row['Price'])
        qty = float(row['Quantity'])
        
        if ticker not in holdings:
            holdings[ticker] = 0.0
            invested[ticker] = 0.0
            
        if action == 'BUY':
            holdings[ticker] += qty
            invested[ticker] += price * qty
        elif action == 'SELL':
            if holdings[ticker] > 0:
                avg_price = invested[ticker] / holdings[ticker]
                invested[ticker] -= avg_price * qty
            holdings[ticker] -= qty

print("Asset | Qty | Invested | Evaluated | Profit")
for t in holdings:
    if holdings[t] > 0:
        eval_amt = holdings[t] * real_prices.get(t, 0.0)
        profit = eval_amt - invested[t]
        print(f"{t}: Qty={holdings[t]} | Inv={invested[t]:,.0f} | Eval={eval_amt:,.0f} | Profit={profit:,.0f}")
