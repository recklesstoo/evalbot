// EvalBot Data Bridge V0.1. Signal-only. Experimental; verify in NinjaTrader 8.
#region Using declarations
using System;
using System.Collections.Concurrent;
using System.ComponentModel.DataAnnotations;
using System.Globalization;
using System.IO;
using System.Net;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using NinjaTrader.NinjaScript;
#endregion
namespace NinjaTrader.NinjaScript.Indicators
{
    public class EvalBotDataBridge : Indicator
    {
        private ConcurrentQueue<string> queue;
        private CancellationTokenSource cancel;
        private int count;
        protected override void OnStateChange()
        {
            if (State == State.SetDefaults)
            {
                Name = "EvalBotDataBridge";
                Description = "Exports closed bars to local EvalBot. Never submits orders.";
                Calculate = Calculate.OnBarClose;
                IsOverlay = true;
                Endpoint = "http://127.0.0.1:8765/api/bar";
                ApiToken = "dev-local-change-me";
                SourceUtcOffsetHours = -5;
                SendHistoricalBars = true;
            }
            else if (State == State.DataLoaded)
            {
                queue = new ConcurrentQueue<string>();
                cancel = new CancellationTokenSource();
                Task.Run(() => Sender(cancel.Token));
            }
            else if (State == State.Terminated && cancel != null) cancel.Cancel();
        }
        protected override void OnBarUpdate()
        {
            if (queue == null || (!SendHistoricalBars && State == State.Historical)) return;
            if (Interlocked.CompareExchange(ref count, 0, 0) >= 1000) return;
            var ci = CultureInfo.InvariantCulture;
            var utc = new DateTimeOffset(DateTime.SpecifyKind(Time[0], DateTimeKind.Unspecified),
                TimeSpan.FromHours(SourceUtcOffsetHours)).ToUniversalTime();
            var symbol = Instrument.FullName.Replace("\\", "\\\\").Replace("\"", "\\\"");
            var json = string.Format(ci,
                "{{\"symbol\":\"{0}\",\"timestamp\":\"{1}\",\"open\":{2},\"high\":{3},\"low\":{4},\"close\":{5},\"volume\":{6},\"tick_size\":{7}}}",
                symbol, utc.ToString("yyyy-MM-ddTHH:mm:ss.fffZ", ci), Open[0], High[0], Low[0], Close[0], Volume[0], TickSize);
            queue.Enqueue(json);
            Interlocked.Increment(ref count);
        }
        private void Sender(CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                string payload;
                if (!queue.TryDequeue(out payload)) { Thread.Sleep(50); continue; }
                Interlocked.Decrement(ref count);
                try
                {
                    var bytes = Encoding.UTF8.GetBytes(payload);
                    var req = (HttpWebRequest)WebRequest.Create(Endpoint);
                    req.Method = "POST";
                    req.ContentType = "application/json";
                    req.Headers["X-EvalBot-Token"] = ApiToken;
                    req.Timeout = 2500;
                    req.ReadWriteTimeout = 2500;
                    req.ContentLength = bytes.Length;
                    using (var s = req.GetRequestStream()) s.Write(bytes, 0, bytes.Length);
                    using (var response = req.GetResponse()) { }
                }
                catch (Exception ex) { Print("EvalBot Bridge: " + ex.Message); Thread.Sleep(1000); }
            }
        }
        [NinjaScriptProperty]
        [Display(Name="Receiver URL", Order=1, GroupName="EvalBot")]
        public string Endpoint { get; set; }
        [NinjaScriptProperty]
        [Display(Name="API Token", Order=2, GroupName="EvalBot")]
        public string ApiToken { get; set; }
        [NinjaScriptProperty]
        [Range(-12,14)]
        [Display(Name="Chart UTC Offset", Order=3, GroupName="EvalBot")]
        public int SourceUtcOffsetHours { get; set; }
        [NinjaScriptProperty]
        [Display(Name="Send historical bars", Order=4, GroupName="EvalBot")]
        public bool SendHistoricalBars { get; set; }
    }
}
