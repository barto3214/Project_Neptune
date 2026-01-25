using Newtonsoft.Json;
using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Net.Sockets;
using System.Text;
using System.Text.Json;
using System.Threading.Tasks;

namespace PN_Ground_Station
{
    /// TCP client for receiving telemetry data from Raspberry Pi
    public class TcpDataClient : IDisposable
    {
        private TcpClient? _client;
        private StreamReader? _reader;
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
                while (!cancellationToken.IsCancellationRequested && _reader != null)
                {
                    var line = await _reader.ReadLineAsync();

                    if (string.IsNullOrWhiteSpace(line))
                        continue;

                    try
                    {
                        // Parse JSON
                        var jsonData = JsonConvert.DeserializeObject<dynamic>(line);

                        var sensorData = new SensorData
                        {
                            StationId = (int)jsonData.station_id,
                            Ph = (double)jsonData.ph,
                            Tds = (double)jsonData.tds,
                            Temperature = (double)jsonData.temperature,
                            Conductivity = (double)jsonData.conductivity,
                            Timestamp = (uint)jsonData.timestamp,
                            BatteryVoltage = (double)jsonData.battery_voltage,
                            ErrorFlags = (byte)jsonData.error_flags,
                            ReceivedAt = DateTime.Parse((string)jsonData.received_at)
                        };

                        // Fire event
                        DataReceived?.Invoke(this, sensorData);
                    }
                    catch (Newtonsoft.Json.JsonException ex)
                    {
                        ErrorOccurred?.Invoke(this, new Exception($"JSON parse error: {ex.Message}"));
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

        public void Dispose()
        {
            Disconnect();
            _cancellationTokenSource?.Dispose();
            _reader?.Dispose();
            _client?.Dispose();
        }
    }
}
