using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;
using PN_Ground_Station.DockWindows;

namespace PN_Ground_Station
{
    /// TCP client for receiving telemetry data from Raspberry Pi
    public class TcpDataClient : IDisposable
    {
        private TcpClient? _client;
        private StreamReader? _reader;
        private StreamWriter? _writer;
        private CancellationTokenSource? _cancellationTokenSource;
        private bool _isConnected;

        public event EventHandler<SensorData>? DataReceived;
        public event EventHandler<string>? ConnectionStatusChanged;
        public event EventHandler<Exception>? ErrorOccurred;

        public bool IsConnected => _isConnected;

        /// Connect to TCP server
        public async Task ConnectAsync(string host, int port)
        {
            try
            {
                _client = new TcpClient();
                await _client.ConnectAsync(host, port);

                var stream = _client.GetStream();
                _reader = new StreamReader(stream, Encoding.UTF8);
                _writer = new StreamWriter(stream, Encoding.UTF8) { AutoFlush = true };

                _isConnected = true;
                ConnectionStatusChanged?.Invoke(this, $"Connected to {host}:{port}");

                // Start receiving loop
                _cancellationTokenSource = new CancellationTokenSource();
                _ = Task.Run(() => ReceiveDataLoop(_cancellationTokenSource.Token));
            }
            catch (Exception ex)
            {
                _isConnected = false;
                ErrorOccurred?.Invoke(this, ex);
                throw;
            }
        }

        /// Disconnect from server
        public void Disconnect()
        {
            _cancellationTokenSource?.Cancel();
            _reader?.Dispose();
            _client?.Close();
            _isConnected = false;
            ConnectionStatusChanged?.Invoke(this, "Disconnected");
        }

        /// Data receiving loop
        private async Task ReceiveDataLoop(CancellationToken cancellationToken)
        {
            try
            {
                System.Diagnostics.Debug.WriteLine("ReceiveDataLoop STARTED");

                while (!cancellationToken.IsCancellationRequested && _reader != null)
                {
                    var line = await _reader.ReadLineAsync();

                    System.Diagnostics.Debug.WriteLine($"[RX] Received line: {line?.Substring(0, Math.Min(50, line?.Length ?? 0))}...");

                    if (string.IsNullOrWhiteSpace(line))
                    {
                        System.Diagnostics.Debug.WriteLine("[RX] Empty line, skipping");
                        continue;
                    }

                    try
                    {
                        // Parse JSON
                        System.Diagnostics.Debug.WriteLine($"[RX] Parsing JSON...");
                        var jsonData = JsonConvert.DeserializeObject<dynamic>(line);

                        // Sprawdź typ wiadomości
                        if (jsonData.status != null)
                        {
                            // To jest odpowiedź na komendę (status message)
                            string status = (string)jsonData.status;
                            string message = jsonData.message != null ? (string)jsonData.message : "";

                            System.Diagnostics.Debug.WriteLine($"[RX] Server response: {status} - {message}");
                            ConnectionStatusChanged?.Invoke(this, message);
                            continue;
                        }

                        // To są dane z czujników - muszą mieć station_id
                        if (jsonData.station_id == null)
                        {
                            System.Diagnostics.Debug.WriteLine($"[RX] Ignoring message without station_id: {line}");
                            continue;
                        }

                        System.Diagnostics.Debug.WriteLine($"[RX] Parsing sensor data...");
                        var sensorData = new SensorData
                        {
                            StationId = (int)jsonData.station_id,
                            Ph = (double)jsonData.ph,
                            Tds = (double)jsonData.tds,
                            Temperature = (double)jsonData.temperature,
                            Conductivity = (double)jsonData.conductivity,
                            Timestamp = (uint)jsonData.timestamp,
                            BatteryVoltage = (double)jsonData.battery_voltage,
                            ErrorFlags = jsonData.error_flags != null ? (byte)jsonData.error_flags : (byte)0,
                            ReceivedAt = DateTime.TryParse((string)jsonData.received_at, out DateTime parsedDate)
                                ? parsedDate
                                : DateTime.Now
                        };

                        // Fire event
                        System.Diagnostics.Debug.WriteLine($"[RX] Firing DataReceived event: pH={sensorData.Ph}, TDS={sensorData.Tds}");
                        DataReceived?.Invoke(this, sensorData);
                        System.Diagnostics.Debug.WriteLine($"[RX] Event fired successfully");
                    }
                    catch (Newtonsoft.Json.JsonException ex)
                    {
                        System.Diagnostics.Debug.WriteLine($"[RX] JSON parse error: {ex.Message}");
                        ErrorOccurred?.Invoke(this, new Exception($"JSON parse error: {ex.Message}"));
                    }
                    catch (Exception ex)
                    {
                        System.Diagnostics.Debug.WriteLine($"[RX] Error processing message: {ex.Message}");
                        System.Diagnostics.Debug.WriteLine($"[RX] Stack trace: {ex.StackTrace}");
                        System.Diagnostics.Debug.WriteLine($"[RX] Message was: {line}");
                    }
                }
            }
            catch (IOException)
            {
                _isConnected = false;
                ConnectionStatusChanged?.Invoke(this, "Connection lost");
            }
            catch (Exception ex)
            {
                ErrorOccurred?.Invoke(this, ex);
            }
        }
        public async Task SendCommandAsync(string command, int param1 = 0, int param2 = 0)
        {
            if (!_isConnected || _writer == null)
            {
                throw new InvalidOperationException("Not connected to server");
            }

            try
            {
                // Przygotuj JSON command
                var commandObj = new
                {
                    command = command.ToLower(),
                    param1,
                    param2,
                    timestamp = DateTime.Now.ToString("o")
                };

                string json = JsonConvert.SerializeObject(commandObj);

                // Wyślij (z newline na końcu)
                await _writer.WriteLineAsync(json);
                await _writer.FlushAsync();

                System.Diagnostics.Debug.WriteLine($"Command sent: {json}");
            }
            catch (Exception ex)
            {
                ErrorOccurred?.Invoke(this, ex);
                throw;
            }
        }
        public void Dispose()
        {
            Disconnect();
            _cancellationTokenSource?.Dispose();
            _reader?.Dispose();
            _client?.Dispose();
        }
    }
    public partial class App
    {
        private TcpDataClient _tcpClient;
        private ChartsWindow _chartsWindow;
        private DataGridWindow _dataGridWindow;
        private CameraWindow _cameraWindow;
        private ControlsWindow _controlsWindow;

        public App()
        {
            _tcpClient = new TcpDataClient();
            _chartsWindow = new ChartsWindow();
            _dataGridWindow = new DataGridWindow();
            _cameraWindow = new CameraWindow();
            _controlsWindow = new ControlsWindow(_tcpClient);
        }
    }
}
