import requests
import pandas as pd
import pandas_ta as ta

def get_klines_df(symbol: str = "BTCUSDT", interval: str = "1h", limit: int = 100) -> pd.DataFrame:
    """Получает свечи с Binance API."""
    url = f"https://api.binance.com/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    response = requests.get(url, timeout=10)
    data = response.json()
    
    if not isinstance(data, list):
        return pd.DataFrame()
        
    df = pd.DataFrame(data, columns=[
        'open_time', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_asset_volume', 'number_of_trades',
        'taker_buy_base_asset_volume', 'taker_buy_quote_asset_volume', 'ignore'
    ])
    
    df['close'] = df['close'].astype(float)
    df['high'] = df['high'].astype(float)
    df['low'] = df['low'].astype(float)
    df['open'] = df['open'].astype(float)
    return df

def find_trade_setup(symbol: str = "BTCUSDT") -> dict | None:
    """
    Анализирует рынок и возвращает сигнал ТОЛЬКО если есть подходящая формация.
    Если качественного сетапа нет — возвращает None.
    """
    try:
        df = get_klines_df(symbol=symbol, interval="1h", limit=100)
        if df.empty:
            return None
        
        # Расчет показателей
        df['RSI'] = ta.rsi(df['close'], length=14)
        macd = ta.macd(df['close'], fast=12, slow=26, signal=9)
        df = pd.concat([df, macd], axis=1)
        
        latest = df.iloc[-1]
        price = round(latest['close'], 2)
        rsi = round(latest['RSI_14'], 2)
        macd_hist = round(latest['MACDh_12_26_9'], 2)
        
        action = None
        formation = ""
        
        # --- ПОИСК ФОРМАЦИИ И ВХОДА ---
        # Формация 1: Бычий разворот (Перепроданность + пересечение MACD вверх)
        if rsi <= 35 and macd_hist > 0:
            action = "LONG 🟢"
            formation = "Бычий разворот (RSI перепродан + подтверждение MACD)"
            stop_loss = round(price * 0.985, 2)
            take_profit = round(price * 1.03, 2)
            
        # Формация 2: Медвежий разворот (Перекупленность + пересечение MACD вниз)
        elif rsi >= 65 and macd_hist < 0:
            action = "SHORT 🔴"
            formation = "Медвежий разворот (RSI перекуплен + подтверждение MACD)"
            stop_loss = round(price * 1.015, 2)
            take_profit = round(price * 0.97, 2)

        # Если формации нет — сигнал не создаем
        if not action:
            return None

        return {
            "symbol": symbol,
            "price": price,
            "action": action,
            "formation": formation,
            "rsi": rsi,
            "stop_loss": stop_loss,
            "take_profit": take_profit
        }
        
    except Exception:
        return None