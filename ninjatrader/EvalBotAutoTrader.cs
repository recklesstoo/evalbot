// EvalBot AutoTrader V0.3 — native NinjaTrader 8 strategy.
// Standalone execution engine: no Python, bridge, or external service required.
// Experimental automatic strategy. No mandatory Sim101 step; validate before deployment.
#region Using declarations
using System;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using NinjaTrader.Cbi;
using NinjaTrader.Data;
using NinjaTrader.NinjaScript;
using NinjaTrader.NinjaScript.Indicators;
using NinjaTrader.NinjaScript.DrawingTools;
#endregion
namespace NinjaTrader.NinjaScript.Strategies
{
    public class EvalBotAutoTrader : Strategy
    {
        private ATR atr;
        private double sessionRealized, sessionStartCumProfit;
        private int tradesToday;
        private DateTime sessionDate = DateTime.MinValue;
        private bool blocked;
        private double entryStopDistance;
        private bool pendingEntry;
        private int lastEntryBar = -1;
        private double carriedRealized;
        private bool stateLoaded, bannerShown;
        private string lastSavedState;
        private bool entryCounted;

        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "EvalBotAutoTrader";
                Description = "Automatic order execution on the selected NinjaTrader account, with stop, target and configurable risk controls. Enabling the strategy authorizes its order submissions; provider rules still apply.";
                Calculate = Calculate.OnBarClose;
                EntriesPerDirection = 1;
                EntryHandling = EntryHandling.AllEntries;
                IsExitOnSessionCloseStrategy = true;
                ExitOnSessionCloseSeconds = 60;
                StopTargetHandling = StopTargetHandling.PerEntryExecution;
                StartBehavior = StartBehavior.WaitUntilFlat;
                RealtimeErrorHandling = RealtimeErrorHandling.StopCancelClose;
                BarsRequiredToTrade = 40;
                IsInstantiatedOnEachOptimizationIteration = true;
                RiskPerTrade = 100;
                DailyLossLimit = 400;
                DailyProfitTarget = 750;
                RewardRisk = 2.0;
                MaxTradesPerDay = 3;
                MaxContracts = 6;
                SweepLookback = 20;
                AtrMultiplier = 1.5;
                SessionStart = 0;
                SessionEnd = 2359;
                EnableAutomaticExecution = true;
            }
            else if (State == State.DataLoaded)
            {
                atr = ATR(14);
            }
        }

        private bool InSession()
        {
            int hhmm = ToTime(Time[0]) / 100;
            return SessionStart <= SessionEnd
                ? hhmm >= SessionStart && hhmm <= SessionEnd
                : hhmm >= SessionStart || hhmm <= SessionEnd;
        }

        protected override void OnBarUpdate()
        {
            if (CurrentBar < Math.Max(BarsRequiredToTrade, SweepLookback + 2))
                return;

            // Calendar-date reset is chart-time based; configure chart time zone deliberately.
            if (Time[0].Date != sessionDate)
            {
                sessionDate = Time[0].Date;
                sessionStartCumProfit = SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;
                sessionRealized = 0;
                tradesToday = 0;
                blocked = false;
                pendingEntry = false;
                carriedRealized = 0;
                stateLoaded = false;
                bannerShown = false;
                lastSavedState = null;
                entryCounted = false;
            }

            if (State == State.Realtime && !stateLoaded)
            {
                stateLoaded = true;
                sessionStartCumProfit = SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit;
                carriedRealized = 0;
                tradesToday = 0;
                blocked = false;
                LoadDailyState();
            }
            if (State == State.Realtime && EnableAutomaticExecution && !bannerShown)
            {
                bannerShown = true;
                string accountName = Account == null ? "Unknown" : Account.Name;
                Print("EvalBot AUTO ON - " + accountName);
                Draw.TextFixed(this, "EvalBotAutoBanner",
                    "EvalBot AUTO ON - " + accountName, TextPosition.TopRight);
            }

            sessionRealized = carriedRealized + SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit - sessionStartCumProfit;
            double unrealized = Position.MarketPosition == MarketPosition.Flat ? 0
                : Position.GetUnrealizedProfitLoss(PerformanceUnit.Currency, Close[0]);
            if (sessionRealized + unrealized <= -DailyLossLimit || sessionRealized + unrealized >= DailyProfitTarget)
            {
                blocked = true;
                if (Position.MarketPosition == MarketPosition.Long) ExitLong("DailyLimit", "EBLong");
                else if (Position.MarketPosition == MarketPosition.Short) ExitShort("DailyLimit", "EBShort");
            }

            SaveDailyState();

            if (blocked || !InSession() || tradesToday >= MaxTradesPerDay
                || Position.MarketPosition != MarketPosition.Flat || pendingEntry)
                return;

            // User enables the strategy on the chosen account and authorizes order submission.
            // Provider permission is separate from user consent.
            if (!EnableAutomaticExecution)
                return;

            double priorHigh = MAX(High, SweepLookback)[1];
            double priorLow = MIN(Low, SweepLookback)[1];
            double tick = TickSize;
            double stopPoints = Math.Ceiling(Math.Max(atr[0] * AtrMultiplier, 4 * tick) / tick) * tick;
            if (stopPoints <= 0 || Instrument.MasterInstrument.PointValue <= 0)
                return;

            // Round down size to stay within configured per-trade risk.
            int qty = Math.Min(MaxContracts,
                (int)Math.Floor(RiskPerTrade / (stopPoints * Instrument.MasterInstrument.PointValue)));
            if (qty < 1) return;

            bool buy = Low[0] < priorLow - tick && Close[0] > priorLow && Close[0] > Open[0];
            bool sell = High[0] > priorHigh + tick && Close[0] < priorHigh && Close[0] < Open[0];
            if (buy == sell) return;

            // Attach protective stop and target BEFORE submitting the entry.
            int stopTicks = Math.Max(4, (int)Math.Round(stopPoints / tick));
            int targetTicks = Math.Max(1, (int)Math.Round(stopTicks * RewardRisk));
            string tag = buy ? "EBLong" : "EBShort";
            SetStopLoss(tag, CalculationMode.Ticks, stopTicks, false);
            SetProfitTarget(tag, CalculationMode.Ticks, targetTicks);
            entryStopDistance = stopPoints;
            pendingEntry = true;
            lastEntryBar = CurrentBar;
            if (buy) EnterLong(qty, tag);
            else EnterShort(qty, tag);
        }


        private string DailyStatePath()
        {
            string account = Account == null ? "unknown" : Account.Name;
            string symbol = Instrument == null ? "unknown" : Instrument.FullName;
            string name = account + "_" + symbol + "_" + sessionDate.ToString("yyyyMMdd", CultureInfo.InvariantCulture);
            foreach (char invalid in Path.GetInvalidFileNameChars()) name = name.Replace(invalid, '_');
            string dir = Path.Combine(NinjaTrader.Core.Globals.UserDataDir, "EvalBotAutoTrader");
            Directory.CreateDirectory(dir);
            return Path.Combine(dir, name + ".state");
        }

        private void LoadDailyState()
        {
            try
            {
                string path = DailyStatePath();
                if (!File.Exists(path)) return;
                string[] parts = File.ReadAllText(path).Trim().Split('|');
                if (parts.Length != 5 || parts[0] != "v1") throw new InvalidDataException("Invalid state");
                tradesToday = int.Parse(parts[1], CultureInfo.InvariantCulture);
                carriedRealized = double.Parse(parts[2], CultureInfo.InvariantCulture);
                blocked = parts[3] == "1" || parts[4] == "1";
                Print("EvalBot restored state: trades=" + tradesToday + " PnL=" + carriedRealized);
            }
            catch (Exception ex)
            {
                blocked = true;
                Print("EvalBot recovery failed; blocked: " + ex.Message);
            }
        }

        private void SaveDailyState()
        {
            if (State != State.Realtime || !stateLoaded) return;
            try
            {
                double realized = carriedRealized +
                    SystemPerformance.AllTrades.TradesPerformance.Currency.CumProfit - sessionStartCumProfit;
                string data = "v1|" + tradesToday.ToString(CultureInfo.InvariantCulture)
                    + "|" + realized.ToString("R", CultureInfo.InvariantCulture)
                    + "|" + (blocked ? "1" : "0")
                    + "|" + (pendingEntry ? "1" : "0");
                if (data == lastSavedState) return;
                string path = DailyStatePath();
                string temp = path + ".tmp";
                File.WriteAllText(temp, data);
                if (File.Exists(path)) File.Replace(temp, path, null);
                else File.Move(temp, path);
                lastSavedState = data;
            }
            catch (Exception ex)
            {
                blocked = true;
                Print("EvalBot state save failed; blocked: " + ex.Message);
            }
        }

        protected override void OnOrderUpdate(Order order, double limitPrice, double stopPrice,
            int quantity, int filled, double averageFillPrice, OrderState orderState,
            DateTime time, ErrorCode error, string comment)
        {
            if (order == null || (order.Name != "EBLong" && order.Name != "EBShort"))
                return;
            if (orderState == OrderState.Rejected || orderState == OrderState.Cancelled)
            {
                pendingEntry = false;
                if (orderState == OrderState.Rejected)
                {
                    blocked = true;
                    Print("EvalBot: entry rejected; trading blocked. " + comment);
                }
            }
        }

        protected override void OnExecutionUpdate(Execution execution, string executionId,
            double price, int quantity, MarketPosition marketPosition, string orderId, DateTime time)
        {
            if (execution == null || execution.Order == null) return;
            if ((execution.Order.Name == "EBLong" || execution.Order.Name == "EBShort")
                && execution.Order.OrderState == OrderState.Filled)
            {
                tradesToday++;
                pendingEntry = false;
            }
        }

        [NinjaScriptProperty]
        [Range(1, 100000)]
        [Display(Name="Risk per trade ($)", Order=1, GroupName="Risk")]
        public double RiskPerTrade { get; set; }
        [NinjaScriptProperty]
        [Range(1, 100000)]
        [Display(Name="Daily loss limit ($)", Order=2, GroupName="Risk")]
        public double DailyLossLimit { get; set; }
        [NinjaScriptProperty]
        [Range(1, 100000)]
        [Display(Name="Daily profit target ($)", Order=3, GroupName="Risk")]
        public double DailyProfitTarget { get; set; }
        [NinjaScriptProperty]
        [Range(0.5, 10)]
        [Display(Name="Reward / Risk", Order=4, GroupName="Risk")]
        public double RewardRisk { get; set; }
        [NinjaScriptProperty]
        [Range(1, 20)]
        [Display(Name="Max trades per day", Order=5, GroupName="Risk")]
        public int MaxTradesPerDay { get; set; }
        [NinjaScriptProperty]
        [Range(1, 100)]
        [Display(Name="Max contracts", Order=6, GroupName="Risk")]
        public int MaxContracts { get; set; }
        [NinjaScriptProperty]
        [Range(5, 200)]
        [Display(Name="Sweep lookback", Order=1, GroupName="Signal")]
        public int SweepLookback { get; set; }
        [NinjaScriptProperty]
        [Range(0.5, 10)]
        [Display(Name="ATR multiplier", Order=2, GroupName="Signal")]
        public double AtrMultiplier { get; set; }
        [NinjaScriptProperty]
        [Range(0, 2359)]
        [Display(Name="Session start HHmm", Order=1, GroupName="Session")]
        public int SessionStart { get; set; }
        [NinjaScriptProperty]
        [Range(0, 2359)]
        [Display(Name="Session end HHmm", Order=2, GroupName="Session")]
        public int SessionEnd { get; set; }
        [NinjaScriptProperty]
        [Display(Name="Automatic order execution", Order=1, GroupName="Execution")]
        public bool EnableAutomaticExecution { get; set; }
    }
}
