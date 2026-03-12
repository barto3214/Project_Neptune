using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Input;

namespace PN_Ground_Station
{
    public class BoatController : IDisposable
    {
        private readonly TcpDataClient _client;

        // Aktualnie wciśnięte klawisze
        private readonly HashSet<Key> _pressedKeys = new();
        private readonly object _keyLock = new();

        // Pętla wysyłania komend (co 100ms gdy klawisz wciśnięty)
        private CancellationTokenSource _cts = new();
        private Task? _sendLoop;

        private int _lastLeft = 100;
        private int _lastRight = 100;

        // Prędkości (0–100)
        private const int SPEED_FULL = 90;   // % przy płynięciu prosto
        private const int SPEED_OUTER = 80;   // % zewnętrzny silnik przy skręcie
        private const int SPEED_INNER = 20;   // % wewnętrzny silnik przy skręcie
        private const int SPEED_STOP = 100;  // Wartość "stop" w protokole (offset 100)

        public bool IsActive { get; private set; } = false;

        public BoatController(TcpDataClient client)
        {
            _client = client;
        }

        

        /// <summary>Włącz sterowanie WSAD</summary>
        public void Activate()
        {
            if (IsActive) return;
            IsActive = true;
            _cts = new CancellationTokenSource();
            _sendLoop = Task.Run(() => SendLoop(_cts.Token));
        }

        /// <summary>Wyłącz sterowanie WSAD i zatrzymaj łódkę</summary>
        public void Deactivate()
        {
            if (!IsActive) return;
            IsActive = false;
            _cts.Cancel();
            lock (_keyLock) _pressedKeys.Clear();
            _ = SendDriveCommand(SPEED_STOP, SPEED_STOP);  
        }

       

        public void OnKeyDown(object sender, KeyEventArgs e)
        {
            if (!IsActive) return;
            var key = e.Key;
            if (key is Key.W or Key.S or Key.A or Key.D or Key.Space)
            {
                lock (_keyLock) _pressedKeys.Add(key);
                e.Handled = true;
            }
        }

        public void OnKeyUp(object sender, KeyEventArgs e)
        {
            if (!IsActive) return;
            lock (_keyLock) _pressedKeys.Remove(e.Key);
            e.Handled = true;
        }

        

        private async Task SendLoop(CancellationToken ct)
        {
            while (!ct.IsCancellationRequested)
            {
                try
                {
                    bool anyKeyPressed;
                    lock (_keyLock) anyKeyPressed = _pressedKeys.Count > 0;
                    var (left, right) = ComputeSpeeds();

                    if (left != _lastLeft || right != _lastRight || anyKeyPressed)
                    {
                        await SendDriveCommand(left, right);
                        _lastLeft = left;
                        _lastRight = right;
                    }

                    await Task.Delay(100, ct);  // 10 komend/s
                }
                catch (OperationCanceledException) { break; }
                catch { /* Błąd połączenia — kontynuuj */ }
            }
        }

        

        /// <summary>
        /// Zwraca (left, right) jako wartości protokołu (0–200, 100=stop)
        /// </summary>
        private (int left, int right) ComputeSpeeds()
        {
            bool w, s, a, d, space;
            lock (_keyLock)
            {
                w = _pressedKeys.Contains(Key.W);
                s = _pressedKeys.Contains(Key.S);
                a = _pressedKeys.Contains(Key.A);
                d = _pressedKeys.Contains(Key.D);
                space = _pressedKeys.Contains(Key.Space);
            }

            // Spacja = STOP awaryjny
            if (space) return (SPEED_STOP, SPEED_STOP);

            // Wyklucz sprzeczne kombinacje
            if (w && s) { w = false; s = false; }
            if (a && d) { a = false; d = false; }

            // Oblicz surowe prędkości -100..+100
            int leftRaw = 0, rightRaw = 0;

            if (w && a) { leftRaw = SPEED_INNER; rightRaw = SPEED_OUTER; }  // Przód + skręt lewo
            else if (w && d) { leftRaw = SPEED_OUTER; rightRaw = SPEED_INNER; }  // Przód + skręt prawo
            else if (s && a) { leftRaw = -SPEED_INNER; rightRaw = -SPEED_OUTER; }  // Tył + skręt lewo
            else if (s && d) { leftRaw = -SPEED_OUTER; rightRaw = -SPEED_INNER; }  // Tył + skręt prawo
            else if (w) { leftRaw = SPEED_FULL; rightRaw = SPEED_FULL; }  // Przód prosto
            else if (s) { leftRaw = -SPEED_FULL; rightRaw = -SPEED_FULL; }  // Tył prosto
            else if (a) { leftRaw = -SPEED_FULL; rightRaw = SPEED_FULL; }  // Obrót w lewo
            else if (d) { leftRaw = SPEED_FULL; rightRaw = -SPEED_FULL; }  // Obrót w prawo
            // else: nic nie wciśnięte = STOP (0,0)

            // Konwersja do protokołu: offset +100, zakres 0–200
            return (leftRaw + SPEED_STOP, rightRaw + SPEED_STOP);
        }

        // ── Wysyłanie przez TCP ──────────────────────────────────────────────

        private async Task SendDriveCommand(int left, int right)
        {
            // CMD_BOAT_DRIVE = 0x20 = 32
            // param1 = prędkość lewego silnika (0–200)
            // param2 = prędkość prawego silnika (0–200)
            await _client.SendCommandAsync("boat_drive", left, right);
        }

        // ── IDisposable ──────────────────────────────────────────────────────

        public void Dispose()
        {
            Deactivate();
            _cts.Dispose();
        }
    }
}