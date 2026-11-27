from datetime import date,timedelta
from app.steady_momentum import technical
from app.technical import Candle,compute

def bars(pump=False):
    close=100.
    result=[]
    for i in range(220):
        close*=1.0035 if i%5<3 else .998
        if pump and i==218:close*=1.2
        result.append(Candle((date(2025,1,1)+timedelta(days=i)).isoformat(),close,close*1.008,close*.992,close,1000000,"ADJUSTED"))
    return result

def test_single_day_pump_rejected():
    c=bars(True)
    assert technical(c,compute(c)) is None

def test_insufficient_history_rejected():
    c=bars()[:200]
    assert technical(c,compute(c)) is None

def test_gradual_bullish_screen_with_controlled_indicator_fixture():
    c=bars()
    indicators=compute(c)
    # Explicit indicator values test the screen independently of indicator math.
    for k,v in {"sma_20":c[-1].close*.99,"sma_50":c[-1].close*.95,
                "sma_200":c[-1].close*.85,"rsi_14":60,"macd":1,"macd_signal":.8,"atr_14":2}.items():
        indicators[k][-1]=v
    row=technical(c,indicators)
    assert row is not None and row["technical_rating"]=="ATLAS_STRONG_BULLISH"
