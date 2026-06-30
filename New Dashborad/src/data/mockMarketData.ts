/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

export interface Candle {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  regime: "bull" | "bear" | "volatile" | "sideways";
}

// Generate realistic mock market data
export const generateMockCandles = (
  symbol: string,
  regime: "bull" | "bear" | "volatile" | "sideways" = "bull",
  count: number = 100
): Candle[] => {
  let basePrice = 150;
  if (symbol === "BTC/USD") basePrice = 60000;
  if (symbol === "EUR/USD") basePrice = 1.08;

  const candles: Candle[] = [];
  let currentPrice = basePrice;
  const startDate = new Date("2026-01-01");

  for (let i = 0; i < count; i++) {
    const dateStr = new Date(startDate.getTime() + i * 24 * 60 * 60 * 1000)
      .toISOString()
      .split("T")[0];

    let changePercent = 0;
    let volFactor = 1;

    switch (regime) {
      case "bull":
        changePercent = (Math.random() - 0.4) * 0.02 + 0.003; // upward bias
        volFactor = 0.8;
        break;
      case "bear":
        changePercent = (Math.random() - 0.6) * 0.02 - 0.004; // downward bias
        volFactor = 1.2;
        break;
      case "volatile":
        changePercent = (Math.random() - 0.5) * 0.05 + (i === count / 2 ? -0.08 : 0); // huge swings, flash crash in the middle
        volFactor = 2.5;
        break;
      case "sideways":
      default:
        changePercent = (Math.random() - 0.5) * 0.012; // tight range
        volFactor = 0.6;
        break;
    }

    const open = currentPrice;
    currentPrice = currentPrice * (1 + changePercent);
    const close = currentPrice;

    const high = Math.max(open, close) * (1 + Math.random() * 0.005 * volFactor);
    const low = Math.min(open, close) * (1 - Math.random() * 0.005 * volFactor);
    const volume = Math.floor((1000000 + Math.random() * 5000000) * volFactor);

    candles.push({
      time: dateStr,
      open,
      high,
      low,
      close,
      volume,
      regime,
    });
  }

  return candles;
};

export const getSampleMarketData = (symbol: string): Candle[] => {
  // Return a continuous stream of different regimes
  const bull = generateMockCandles(symbol, "bull", 40);
  const volatile = generateMockCandles(symbol, "volatile", 20);
  const bear = generateMockCandles(symbol, "bear", 30);
  const sideways = generateMockCandles(symbol, "sideways", 30);

  // Concatenate them, adjusting starting prices to make it continuous
  const allCandles: Candle[] = [];
  let lastClose = 0;

  [bull, volatile, bear, sideways].forEach((regimeCandles, regimeIdx) => {
    regimeCandles.forEach((c, idx) => {
      if (regimeIdx === 0 && idx === 0) {
        allCandles.push(c);
        lastClose = c.close;
      } else {
        const factor = lastClose / c.open;
        const adjustedCandle: Candle = {
          ...c,
          open: lastClose,
          high: c.high * factor,
          low: c.low * factor,
          close: c.close * factor,
        };
        allCandles.push(adjustedCandle);
        lastClose = adjustedCandle.close;
      }
    });
  });

  return allCandles;
};
