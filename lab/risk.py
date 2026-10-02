"""Risk allocation based exclusively on information available at the close."""
import numpy as np
import pandas as pd


def risk_history(snapshot, config):
    result = pd.DataFrame({"date": snapshot.calendar, "target_exposure": config.exposure,
                           "market_close": np.nan, "market_ma": np.nan, "market_volatility": np.nan,
                           "trend_allowed": True})
    if not config.market_filter and not config.volatility_control:
        return result
    if snapshot.market.empty:
        raise ValueError("Market reference data is required for the selected risk controls")
    market = snapshot.market.set_index("date").close.reindex(snapshot.calendar)
    ma = market.rolling(config.market_ma).mean()
    vol = market.pct_change(fill_method=None).rolling(20).std(ddof=1) * np.sqrt(252)
    result["market_close"], result["market_ma"], result["market_volatility"] = market.to_numpy(), ma.to_numpy(), vol.to_numpy()
    if config.market_filter:
        result["trend_allowed"] = (market >= ma).to_numpy()
        result["target_exposure"] *= np.where(result.trend_allowed, 1., config.defensive_exposure)
        result.loc[ma.isna().to_numpy(), "target_exposure"] = 0.
    if config.volatility_control:
        scale = (config.target_volatility / vol.replace(0, np.nan)).clip(upper=1).fillna(0)
        result["target_exposure"] *= scale.to_numpy()
    relevant = result[(result.date >= str(config.start)) & (result.date <= str(config.end))]
    if relevant.market_close.isna().any():
        raise ValueError("Market reference does not cover every evaluation session")
    return result
