import React from "react";
import { useSocket } from "../context/SocketContext.js";
import { SystemHealth } from "./SystemHealth.js";
import { PairCards } from "./PairCards.js";
import { LiveChart } from "./LiveChart.js";
import { PipelineGrid } from "./PipelineGrid.js";
import { ActiveTradeCard } from "./ActiveTradeCard.js";
import { RejectionsAndAnalytics } from "./RejectionsAndAnalytics.js";
import { StrategyGuide } from "./StrategyGuide.js";
import { EventStream } from "./EventStream.js";
import { TradesTable } from "./TradesTable.js";
import { SvosQuantLab } from "./SvosQuantLab.js";
import { SMCStatus } from "../types.js";
import { ArrowRight, BookOpen, RefreshCw, Layers } from "lucide-react";

export const SvosResearchDashboard: React.FC = () => {
  const { 
    state, 
    isConnected, 
    resetAnalytics, 
    selectPair, 
    forceCloseTrade 
  } = useSocket();

  if (!state) return null;

  const selectedPairState = state.pairs[state.selectedPair] || Object.values(state.pairs)[0];

  const getTimelineSteps = () => {
    if (!selectedPairState) return [];
    const pipe = selectedPairState.pipeline;
    return [
      { id: "sweep", label: "Liquidity Sweep", active: pipe.liquiditySweep.status === SMCStatus.PASSED },
      { id: "choch", label: "CHoCH Breaker", active: pipe.choch.status === SMCStatus.PASSED },
      { id: "bos", label: "BOS Close", active: pipe.bos.status === SMCStatus.PASSED },
      { id: "ob", label: "Order Block", active: pipe.orderBlock.status === SMCStatus.PASSED },
      { id: "fvg", label: "Fair Value Gap", active: pipe.fvg.status === SMCStatus.PASSED },
      { id: "confluence", label: "Kill Zone / Confluence", active: pipe.confluence.status === SMCStatus.PASSED && pipe.killZone.status === SMCStatus.PASSED },
      { id: "exec", label: "Execution Position", active: !!state.activeTrade || (state.history.length > 0 && state.history[0].pair === selectedPairState.symbol && new Date(state.history[0].exitTime).getTime() > Date.now() - 30000) }
    ];
  };

  const timelineSteps = getTimelineSteps();

  return (
    <div className="w-full flex flex-col gap-6" id="svos-research-dashboard">
      
      {/* Real-time Strategy Timeline Tracker */}
      {selectedPairState && (
        <div className="w-full bg-zinc-900 border border-zinc-800/80 rounded-2xl p-4 shadow-xl flex flex-col gap-3 font-sans">
          <div className="flex items-center justify-between text-[11px] font-bold text-zinc-400 uppercase tracking-widest border-b border-zinc-850 pb-2">
            <span className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-emerald-400 animate-pulse" />
              Selected Pair: <strong className="text-white font-black">{state.selectedPair}</strong>
            </span>
            <span>SVOS Validation Cycle Progression</span>
          </div>
          {/* Timeline chevrons */}
          <div className="flex flex-col sm:flex-row items-center gap-1.5 sm:gap-2 mt-1 w-full justify-between">
            {timelineSteps.map((step, idx) => (
              <React.Fragment key={step.id}>
                <div
                  className={`flex-1 flex items-center justify-center text-center p-2.5 rounded-xl text-xs font-bold border transition-all duration-300 w-full sm:w-auto ${
                    step.active
                      ? "bg-emerald-500/15 border-emerald-500/40 text-emerald-400 shadow shadow-emerald-500/5 scale-[1.01]"
                      : "bg-zinc-950/40 border-zinc-850 text-zinc-500"
                  }`}
                >
                  <span className="font-mono text-[10px] mr-1.5 text-zinc-600">{(idx + 1).toString().padStart(2, "0")}</span>
                  {step.label}
                </div>
                {idx < timelineSteps.length - 1 && (
                  <ArrowRight className="w-3.5 h-3.5 text-zinc-700 hidden sm:block shrink-0" />
                )}
              </React.Fragment>
            ))}
          </div>
        </div>
      )}

      {/* Interactive SVOS Quant Research & Validation Laboratory */}
      <SvosQuantLab />

      {/* BENTO LAYOUT STAGE */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6 items-start">
        {/* Left Column (Width: 1x) */}
        <div className="flex flex-col gap-6">
          {/* Pair Quick Selector Cards */}
          <PairCards
            pairs={state.pairs}
            selectedPair={state.selectedPair}
            onSelectPair={(symbol) => selectPair(symbol)}
          />

          {/* Active Pre-trade & Trade Decision Card */}
          <ActiveTradeCard
            activeTrade={state.activeTrade}
            selectedPairState={selectedPairState}
            onForceClose={forceCloseTrade}
            isPaused={state.isTradingPaused}
          />
        </div>

        {/* Center & Right Column (Width: 2x) */}
        <div className="lg:col-span-2 flex flex-col gap-6">
          {/* Technical SVG overlay Chart */}
          {selectedPairState && (
            <LiveChart pair={selectedPairState} activeTrade={state.activeTrade} />
          )}

          {/* Pipeline State Grid */}
          {selectedPairState && (
            <PipelineGrid pipeline={selectedPairState.pipeline} />
          )}
        </div>
      </div>

      {/* Dynamic logs, analytics rejections */}
      <RejectionsAndAnalytics
        rejections={state.rejections}
        analytics={state.analytics}
        onResetStats={resetAnalytics}
      />

      {/* Event Logs Stream Console */}
      <EventStream events={state.events} />

      {/* Strategy Guide educational card */}
      <StrategyGuide />

      {/* Past Trades Archive */}
      <TradesTable history={state.history} />
    </div>
  );
};
