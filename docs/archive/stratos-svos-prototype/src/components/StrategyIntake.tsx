/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from "react";
import { Brain, Cpu, FileText, Play, CheckCircle, AlertTriangle, RefreshCw } from "lucide-react";
import { StrategyRules } from "../types";

interface StrategyIntakeProps {
  onAddStrategy: (name: string, description: string, rules: StrategyRules) => Promise<void>;
  onClose: () => void;
}

export default function StrategyIntake({ onAddStrategy, onClose }: StrategyIntakeProps) {
  const [idea, setIdea] = useState("");
  const [isParsing, setIsParsing] = useState(false);
  const [parsedResult, setParsedResult] = useState<any | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadingStep, setLoadingStep] = useState(0);

  const sampleIdeas = [
    {
      title: "RSI Mean Reversion (Crypto)",
      text: "Buy BTC/USD on 15M chart if RSI(14) falls below 30, confirming extreme oversold levels. Sell/exit position if RSI crosses back above 70 or price moves down by 1.5% stop loss. Use take profit of 5%. If there's high volatility, halve the position size to 5%."
    },
    {
      title: "MACD Trend Rider (Equity)",
      text: "Trade AAPL stock on 1H chart. Enter long when MACD line crosses above Signal line, provided both are below zero. Stop loss is 3% and take profit is 10%. Position size limit is 15%. Oh, and we should exit if MACD crosses back below Signal line, but wait: if SMA(200) is sloped down, let's reject the trade entirely."
    }
  ];

  const simulateLoading = () => {
    const steps = [
      "Establishing connection to server-side Gemini 3.5 engine...",
      "Extracting token semantic trees and rule syntax...",
      "Verifying parameter consistency against asset requirements...",
      "Conducting rigorous logical audit for latent contradictions...",
      "Compiling final machine-readable strategy blueprint..."
    ];

    setLoadingStep(0);
    const interval = setInterval(() => {
      setLoadingStep(prev => {
        if (prev >= steps.length - 1) {
          clearInterval(interval);
          return prev;
        }
        return prev + 1;
      });
    }, 900);

    return () => clearInterval(interval);
  };

  const handleParse = async () => {
    if (!idea.trim()) return;
    setIsParsing(true);
    setParsedResult(null);
    setError(null);
    
    const stopSim = simulateLoading();

    try {
      const response = await fetch("/api/gemini/parse", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({ idea })
      });

      if (!response.ok) {
        const errData = await response.json();
        throw new Error(errData.error || "Failed to parse strategy idea.");
      }

      const data = await response.json();
      setParsedResult(data);
    } catch (err: any) {
      console.error(err);
      setError(err.message || "An unexpected error occurred during AI parsing.");
    } finally {
      setIsParsing(false);
    }
  };

  const handleCommit = async () => {
    if (!parsedResult) return;
    try {
      await onAddStrategy(
        parsedResult.name,
        parsedResult.description,
        parsedResult.rules
      );
      onClose();
    } catch (err: any) {
      setError(err.message || "Failed to commit strategy to registry.");
    }
  };

  const loadingSteps = [
    "Establishing connection to server-side Gemini 3.5 engine...",
    "Extracting token semantic trees and rule syntax...",
    "Verifying parameter consistency against asset requirements...",
    "Conducting rigorous logical audit for latent contradictions...",
    "Compiling final machine-readable strategy blueprint..."
  ];

  return (
    <div className="bg-slate-50 dark:bg-slate-950 border border-slate-200 dark:border-slate-850 rounded-lg p-6 mb-8 shadow-sm transition-colors duration-200">
      <div className="flex justify-between items-center mb-6">
        <div className="flex items-center space-x-2">
          <Brain className="h-5 w-5 text-slate-800 dark:text-slate-200" />
          <h2 className="font-display font-semibold text-slate-900 dark:text-slate-100 text-lg">AI-Assisted Strategy Intake Workstation</h2>
        </div>
        <button
          onClick={onClose}
          className="text-xs font-mono text-slate-400 hover:text-slate-600 dark:text-slate-450 dark:hover:text-slate-200 px-2 py-1 border border-slate-200 dark:border-slate-850 hover:border-slate-300 dark:hover:border-slate-705 rounded bg-white dark:bg-slate-900 transition-colors cursor-pointer"
          id="intake-cancel-btn"
        >
          [ CLOSE ]
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Hand: Input Panel */}
        <div className="lg:col-span-6 flex flex-col space-y-4">
          <div>
            <label className="block text-xs font-mono text-slate-500 uppercase tracking-wider mb-2">
              Input Strategy Description (Unstructured Text)
            </label>
            <textarea
              value={idea}
              onChange={(e) => setIdea(e.target.value)}
              placeholder="Specify asset class, symbols, technical entries/exits, timeframe, and stop loss / take profit parameters. Be as descriptive as possible..."
              className="w-full h-64 font-sans text-sm text-slate-900 dark:text-slate-100 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-805 rounded-md p-4 focus:ring-1 focus:ring-slate-900 dark:focus:ring-slate-100 focus:border-slate-900 dark:focus:border-slate-100 outline-none resize-none transition-all"
              id="intake-text-input"
            />
          </div>

          <div>
            <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 uppercase tracking-wide block mb-2">
              Or load an institutional template idea:
            </span>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              {sampleIdeas.map((sample, idx) => (
                <button
                  key={idx}
                  onClick={() => setIdea(sample.text)}
                  className="text-left border border-slate-200 dark:border-slate-805 hover:border-slate-300 dark:hover:border-slate-700 bg-white dark:bg-slate-900 p-3 rounded-md text-xs hover:bg-slate-50 dark:hover:bg-slate-850/50 cursor-pointer transition-all group"
                  id={`load-sample-${idx}`}
                >
                  <span className="font-semibold text-slate-800 dark:text-slate-200 block mb-1 group-hover:text-slate-900 dark:group-hover:text-slate-50">
                    {sample.title}
                  </span>
                  <span className="text-slate-500 dark:text-slate-405 line-clamp-2">{sample.text}</span>
                </button>
              ))}
            </div>
          </div>

          <button
            onClick={handleParse}
            disabled={isParsing || !idea.trim()}
            className="flex items-center justify-center space-x-2 w-full bg-slate-900 dark:bg-slate-100 hover:bg-slate-800 dark:hover:bg-slate-200 text-white dark:text-slate-900 py-3 px-4 rounded-md text-sm font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
            id="intake-ai-audit-btn"
          >
            {isParsing ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" />
                <span>Running AI Audit & Blueprinting...</span>
              </>
            ) : (
              <>
                <Play className="h-4 w-4" />
                <span>Trigger AI Audit & Parsing</span>
              </>
            )}
          </button>
        </div>

        {/* Right Hand: Output / Review Panel */}
        <div className="lg:col-span-6 flex flex-col justify-between border border-slate-200 dark:border-slate-805 bg-white dark:bg-slate-900 rounded-md p-5 min-h-[400px] transition-colors duration-200">
          {isParsing && (
            <div className="flex flex-col justify-center items-center h-full py-16 space-y-4">
              <Cpu className="h-8 w-8 text-slate-600 dark:text-slate-400 animate-pulse" />
              <div className="w-48 bg-slate-100 dark:bg-slate-800 h-1.5 rounded-full overflow-hidden">
                <div
                  className="bg-slate-900 dark:bg-slate-200 h-full transition-all duration-700"
                  style={{ width: `${((loadingStep + 1) / loadingSteps.length) * 100}%` }}
                />
              </div>
              <p className="text-xs font-mono text-slate-500 dark:text-slate-400 animate-pulse text-center max-w-xs px-4">
                {loadingSteps[loadingStep]}
              </p>
            </div>
          )}

          {!isParsing && !parsedResult && !error && (
            <div className="flex flex-col justify-center items-center h-full py-16 text-slate-400 dark:text-slate-500">
              <FileText className="h-10 w-10 stroke-[1.2] mb-3" />
              <p className="text-sm font-medium">Awaiting strategy specification input...</p>
              <p className="text-xs text-slate-500 dark:text-slate-550 mt-1 max-w-xs text-center">
                Submit an unstructured idea on the left to invoke the AI parsing and logical audit pipeline.
              </p>
            </div>
          )}

          {error && (
            <div className="flex flex-col justify-center items-center h-full py-16 text-red-500 dark:text-red-405 px-6 text-center">
              <AlertTriangle className="h-8 w-8 mb-2" />
              <p className="text-sm font-semibold">Audit Blocked</p>
              <p className="text-xs text-red-600 dark:text-red-405 mt-1">{error}</p>
            </div>
          )}

          {parsedResult && (
            <div className="space-y-5 flex-1 overflow-y-auto max-h-[480px] pr-1">
              {/* Parsed Specs Header */}
              <div className="border-b border-slate-100 dark:border-slate-800 pb-3">
                <div className="flex justify-between items-start">
                  <div>
                    <span className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 font-bold tracking-wider uppercase bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-200 dark:border-emerald-900/30 px-1.5 py-0.5 rounded">
                      Blueprint Compiled
                    </span>
                    <h3 className="font-display font-bold text-slate-900 dark:text-slate-100 text-lg mt-1.5">
                      {parsedResult.name}
                    </h3>
                  </div>
                  <div className="text-right">
                    <span className="text-[10px] font-mono text-slate-400 dark:text-slate-500 block uppercase">Completeness</span>
                    <span className={`text-base font-mono font-bold ${parsedResult.audit.score >= 80 ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-450"}`}>
                      {parsedResult.audit.score}/100
                    </span>
                  </div>
                </div>
                <p className="text-xs text-slate-600 dark:text-slate-400 mt-2 italic">{parsedResult.description}</p>
              </div>

              {/* Extracted Rules */}
              <div className="grid grid-cols-3 gap-3 bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-850 p-3 rounded-md font-mono text-[10px]">
                <div>
                  <span className="text-slate-400 dark:text-slate-500 block uppercase">Asset Class</span>
                  <span className="text-slate-800 dark:text-slate-200 font-bold">{parsedResult.rules.assetClass}</span>
                </div>
                <div>
                  <span className="text-slate-400 dark:text-slate-500 block uppercase">Symbol</span>
                  <span className="text-slate-800 dark:text-slate-200 font-bold">{parsedResult.rules.symbol}</span>
                </div>
                <div>
                  <span className="text-slate-400 dark:text-slate-500 block uppercase">Timeframe</span>
                  <span className="text-slate-800 dark:text-slate-200 font-bold">{parsedResult.rules.timeframe}</span>
                </div>
              </div>

              <div className="space-y-3">
                <div>
                  <h4 className="text-xs font-mono font-semibold text-slate-800 dark:text-slate-200 uppercase tracking-wider mb-1.5">
                    Entry Signals
                  </h4>
                  <ul className="list-disc list-inside space-y-1 text-xs text-slate-600 dark:text-slate-400">
                    {parsedResult.rules.entryConditions.map((cond: string, idx: number) => (
                      <li key={idx} className="leading-relaxed">{cond}</li>
                    ))}
                  </ul>
                </div>

                <div>
                  <h4 className="text-xs font-mono font-semibold text-slate-800 dark:text-slate-200 uppercase tracking-wider mb-1.5">
                    Exit Signals
                  </h4>
                  <ul className="list-disc list-inside space-y-1 text-xs text-slate-600 dark:text-slate-400">
                    {parsedResult.rules.exitConditions.map((cond: string, idx: number) => (
                      <li key={idx} className="leading-relaxed">{cond}</li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Logical Audit Defects */}
              <div className="border-t border-slate-100 dark:border-slate-800 pt-4">
                <h4 className="text-xs font-mono font-bold text-slate-800 dark:text-slate-200 uppercase tracking-wider mb-2 flex items-center space-x-1.5">
                  <Cpu className="h-3.5 w-3.5 text-indigo-600 dark:text-indigo-400" />
                  <span>AI Logical Audit Results</span>
                </h4>

                {parsedResult.audit.logicalDefects.length === 0 ? (
                  <div className="bg-emerald-50 dark:bg-emerald-950/20 border border-emerald-100 dark:border-emerald-900/30 rounded p-3 text-[11px] text-emerald-800 dark:text-emerald-400 flex items-start space-x-2">
                    <CheckCircle className="h-4 w-4 text-emerald-600 dark:text-emerald-450 shrink-0 mt-0.5" />
                    <div>
                      <p className="font-semibold text-emerald-800 dark:text-emerald-350">Zero logical defects detected.</p>
                      <p className="mt-0.5 text-emerald-700 dark:text-emerald-450">Rules are fully specified and internally consistent.</p>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-2">
                    {parsedResult.audit.logicalDefects.map((defect: any, idx: number) => (
                      <div
                        key={idx}
                        className={`border rounded p-3 text-[11px] ${
                          defect.severity === "high"
                            ? "bg-red-50 dark:bg-red-950/15 border-red-200 dark:border-red-900/30 text-red-900 dark:text-red-455"
                            : "bg-amber-50 dark:bg-amber-950/15 border-amber-200 dark:border-amber-900/30 text-amber-900 dark:text-amber-455"
                        }`}
                      >
                        <div className="flex items-start space-x-2">
                          <AlertTriangle className={`h-4 w-4 shrink-0 mt-0.5 ${defect.severity === "high" ? "text-red-600" : "text-amber-600"}`} />
                          <div>
                            <p className="font-bold flex items-center space-x-1.5">
                              <span>[{defect.type.toUpperCase()}]</span>
                              <span>{defect.title}</span>
                            </p>
                            <p className="mt-1 text-slate-700 dark:text-slate-300 font-sans leading-relaxed">{defect.description}</p>
                            <p className="mt-1 text-[10px] text-slate-500 dark:text-slate-450 italic">Affected: "{defect.affectedRule}"</p>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* recommendations */}
              {parsedResult.audit.recommendations.length > 0 && (
                <div className="bg-slate-50 dark:bg-slate-950 border border-slate-100 dark:border-slate-850 p-3 rounded text-[11px] text-slate-700 dark:text-slate-300 space-y-1">
                  <p className="font-bold font-mono text-[10px] text-slate-500 dark:text-slate-450 uppercase tracking-wider mb-1">Recommendations:</p>
                  <ul className="list-disc list-inside space-y-0.5">
                    {parsedResult.audit.recommendations.map((rec: string, idx: number) => (
                      <li key={idx}>{rec}</li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Commit Controls */}
              <div className="border-t border-slate-100 dark:border-slate-800 pt-4 flex justify-end space-x-2">
                <button
                  onClick={() => setParsedResult(null)}
                  className="px-3 py-1.5 border border-slate-200 dark:border-slate-805 hover:border-slate-300 dark:hover:border-slate-700 text-slate-600 dark:text-slate-400 text-xs font-mono uppercase bg-white dark:bg-slate-900 rounded-md cursor-pointer transition-colors"
                  id="intake-reset-btn"
                >
                  Discard
                </button>
                <button
                  onClick={handleCommit}
                  className="px-4 py-1.5 bg-slate-900 dark:bg-slate-100 hover:bg-slate-800 dark:hover:bg-slate-200 text-white dark:text-slate-900 text-xs font-mono uppercase rounded-md flex items-center space-x-1.5 cursor-pointer transition-colors"
                  id="intake-commit-btn"
                >
                  <CheckCircle className="h-3.5 w-3.5" />
                  <span>Commit to Registry</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
