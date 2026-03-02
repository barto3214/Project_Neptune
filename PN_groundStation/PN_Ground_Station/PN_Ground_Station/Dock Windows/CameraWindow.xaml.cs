using System;
using System.IO;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media.Imaging;

namespace PN_Ground_Station.DockWindows
{
    public partial class CameraWindow : UserControl
    {
        private HttpClient _httpClient;
        private CancellationTokenSource _cts;
        private bool _isStreaming = false;

        public CameraWindow()
        {
            InitializeComponent();
        }

        // ── Połącz ───────────────────────────────────────────────────────────

        private void BtnConnect_Click(object sender, RoutedEventArgs e)
        {
            string ip = txtStreamUrl.Text.Trim();
            string url = $"http://{ip}:8080/stream";
            StartStream(url);
        }

        private void BtnDisconnect_Click(object sender, RoutedEventArgs e)
        {
            StopStream();
        }

        // ── Start / Stop ─────────────────────────────────────────────────────

        private void StartStream(string url)
        {
            if (_isStreaming) StopStream();

            _httpClient = new HttpClient();
            _httpClient.Timeout = Timeout.InfiniteTimeSpan;

            _cts = new CancellationTokenSource();
            _isStreaming = true;

            SetStatus(true);

            Task.Run(() => StreamLoop(url, _cts.Token));
        }

        private void StopStream()
        {
            _isStreaming = false;
            _cts?.Cancel();
            _httpClient?.Dispose();
            _httpClient = null;

            Dispatcher.Invoke(() =>
            {
                imgCamera.Visibility = Visibility.Collapsed;
                pnlPlaceholder.Visibility = Visibility.Visible;
                SetStatus(false);
            });
        }

        // ── Pętla odbierania ─────────────────────────────────────────────────

        private async Task StreamLoop(string url, CancellationToken ct)
        {
            try
            {
                // Otwórz połączenie HTTP — to połączenie nigdy się nie zamknie
                using var response = await _httpClient.GetAsync(
                    url,
                    HttpCompletionOption.ResponseHeadersRead,
                    ct
                );

                using var stream = await response.Content.ReadAsStreamAsync();

                var buffer = new byte[65536]; // 64KB bufor odczytu
                var accum = new MemoryStream();

                // Znaczniki początku i końca JPEG-a
                byte[] SOI = { 0xFF, 0xD8 }; // Start Of Image
                byte[] EOI = { 0xFF, 0xD9 }; // End Of Image

                while (!ct.IsCancellationRequested)
                {
                    // Czytaj kolejne bajty ze strumienia HTTP
                    int bytesRead = await stream.ReadAsync(buffer, 0, buffer.Length, ct);
                    if (bytesRead == 0) break;

                    accum.Write(buffer, 0, bytesRead);
                    byte[] data = accum.ToArray();

                    // Szukaj kompletnego JPEG-a w buforze
                    int start = FindSequence(data, SOI, 0);
                    if (start == -1) continue;

                    int end = FindSequence(data, EOI, start + 2);
                    if (end == -1) continue;

                    // Wytnij bajty od FF D8 do FF D9 (włącznie)
                    int jpegLen = end - start + 2;
                    byte[] jpegData = new byte[jpegLen];
                    Array.Copy(data, start, jpegData, 0, jpegLen);

                    // Zostaw w buforze to co było po końcu tego JPEG-a
                    byte[] remaining = new byte[data.Length - (end + 2)];
                    Array.Copy(data, end + 2, remaining, 0, remaining.Length);
                    accum = new MemoryStream();
                    accum.Write(remaining, 0, remaining.Length);

                    // Wyświetl klatkę na wątku UI
                    DisplayFrame(jpegData);
                }
            }
            catch (OperationCanceledException)
            {
                // Normalne zatrzymanie — nic nie rób
            }
            catch (Exception ex)
            {
                Dispatcher.Invoke(() =>
                {
                    txtStatus.Text = $"● Błąd: {ex.Message}";
                    txtStatus.Foreground = System.Windows.Media.Brushes.Orange;
                    //StopStream();
                });
            }
        }

        // ── Wyświetlanie klatki ───────────────────────────────────────────────

        private void DisplayFrame(byte[] jpegData)
        {
            // Przełącz na wątek UI (WPF wymaga aktualizacji UI z UI thread)
            Dispatcher.Invoke(() =>
            {
                try
                {
                    var bitmap = new BitmapImage();
                    bitmap.BeginInit();
                    bitmap.StreamSource = new MemoryStream(jpegData);
                    bitmap.CacheOption = BitmapCacheOption.OnLoad;
                    bitmap.EndInit();
                    bitmap.Freeze(); // Ważne — pozwala używać obiektu między wątkami

                    imgCamera.Source = bitmap;
                    imgCamera.Visibility = Visibility.Visible;
                    pnlPlaceholder.Visibility = Visibility.Collapsed;
                }
                catch
                {
                    // Uszkodzona klatka — pomiń, nie crashuj
                }
            });
        }

        // ── Pomocnicza: szukaj sekwencji bajtów ──────────────────────────────

        private static int FindSequence(byte[] data, byte[] pattern, int startIndex)
        {
            for (int i = startIndex; i <= data.Length - pattern.Length; i++)
            {
                bool found = true;
                for (int j = 0; j < pattern.Length; j++)
                {
                    if (data[i + j] != pattern[j]) { found = false; break; }
                }
                if (found) return i;
            }
            return -1;
        }

        // ── UI helpers ────────────────────────────────────────────────────────

        private void SetStatus(bool connected)
        {
            if (connected)
            {
                txtStatus.Text = "● Połączono";
                txtStatus.Foreground = System.Windows.Media.Brushes.LimeGreen;
                btnConnect.IsEnabled = false;
                btnDisconnect.IsEnabled = true;
            }
            else
            {
                txtStatus.Text = "● Rozłączono";
                txtStatus.Foreground = System.Windows.Media.Brushes.OrangeRed;
                btnConnect.IsEnabled = true;
                btnDisconnect.IsEnabled = false;
            }
        }
    }
}
