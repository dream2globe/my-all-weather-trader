import csv

holdings = {}
invested = {}

with open('data/actual_trades.csv', 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        ticker = row['Ticker']
        action = row['Action']
        price = float(row['Price'])
        qty = float(row['Quantity'])
        
        if ticker not in ['278530.KS', '069500.KS']: continue
        
        if ticker not in holdings:
            holdings[ticker] = 0
            invested[ticker] = 0
            
        if action == 'BUY':
            holdings[ticker] += qty
            invested[ticker] += price * qty
        elif action == 'SELL':
            if holdings[ticker] > 0:
                avg_price = invested[ticker] / holdings[ticker]
                invested[ticker] -= avg_price * qty
            holdings[ticker] -= qty
            
for t in holdings:
    print(f"{t}: Qty={holdings[t]}, Invested={invested[t]}")
