using System.Text;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Navigation;
using System.Windows.Shapes;
using NetDock.Controls;
using NetDock.Enums;
using PN_Ground_Station.DockWindows;

namespace PN_Ground_Station
{
    public partial class MainWindow : Window
    {
        private readonly TcpDataClient _tcpClient;
        private readonly List<SensorData> _dataHistory = new();
        private int _packetCount = 0;

        // Dock window references
        private ChartsWindow? _chartsWindow;
        private DataGridWindow? _dataGridWindow;
        private CameraWindow? _cameraWindow;
        private ControlsWindow? _controlsWindow;

        public MainWindow()
        {
            InitializeComponent();

            _tcpClient = new TcpDataClient();
            _tcpClient.DataReceived += OnDataReceived;
            _tcpClient.ConnectionStatusChanged += OnConnectionStatusChanged;
            _tcpClient.ErrorOccurred += OnErrorOccurred;
        }

        private void Window_Loaded(object sender, RoutedEventArgs e)
        {
            // Initialize dock windows
            InitializeDockWindows();

            txtStatusMessage.Text = "Ready. Configure connection and click Connect.";
        }

        private void InitializeDockWindows()
        {
            // Create dock windows
            _chartsWindow = new ChartsWindow();
            _dataGridWindow = new DataGridWindow();
            _cameraWindow = new CameraWindow();
            _controlsWindow = new ControlsWindow();

            // Add to dock surface
            var chartsItem = new DockItem(_chartsWindow) { TabName = "📊 Charts" };
            var dataGridItem = new DockItem(_dataGridWindow) { TabName = "📜 Data History" };
            var cameraItem = new DockItem(_cameraWindow) { TabName = "📷 Camera" };
            var controlsItem = new DockItem(_controlsWindow) { TabName = "⚙️ Controls" };

            dockSurface.Add(chartsItem, DockDirection.Top);
            dockSurface.Add(dataGridItem, DockDirection.Bottom);
            dockSurface.Add(cameraItem, DockDirection.Left);
            dockSurface.Add(controlsItem, DockDirection.Right);
        }

        private async void BtnConnect_Click(object sender, RoutedEventArgs e)
        {
            try
            {
                string host = txtServerAddress.Text.Trim();
                if (!int.TryParse(txtServerPort.Text.Trim(), out int port))
                {
                    MessageBox.Show("Invalid port number!", "Error", MessageBoxButton.OK, MessageBoxImage.Error);
                    return;
                }

                btnConnect.IsEnabled = false;
                txtStatusMessage.Text = $"Connecting to {host}:{port}...";

                await _tcpClient.ConnectAsync(host, port);

                btnConnect.IsEnabled = false;
                btnDisconnect.IsEnabled = true;
                connectionIndicator.Fill = Brushes.LimeGreen;
                txtConnectionStatus.Text = "Connected";
            }
            catch (Exception ex)
            {
                btnConnect.IsEnabled = true;
                connectionIndicator.Fill = Brushes.Red;
                txtConnectionStatus.Text = "Connection Failed";
                txtStatusMessage.Text = $"Connection error: {ex.Message}";
                MessageBox.Show($"Failed to connect:\n{ex.Message}", "Connection Error",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
        }

        private void BtnDisconnect_Click(object sender, RoutedEventArgs e)
        {
            _tcpClient.Disconnect();

            btnConnect.IsEnabled = true;
            btnDisconnect.IsEnabled = false;
            connectionIndicator.Fill = Brushes.Red;
            txtConnectionStatus.Text = "Disconnected";
            txtStatusMessage.Text = "Disconnected from server.";
        }

        private void OnDataReceived(object? sender, SensorData data)
        {
            // Execute on UI thread
            Dispatcher.Invoke(() =>
            {
                _packetCount++;
                _dataHistory.Add(data);

                // Keep only last 50 records
                if (_dataHistory.Count > 50)
                    _dataHistory.RemoveAt(0);

                // Update status bar
                txtLastDataTime.Text = data.ReceivedAt.ToString("HH:mm:ss");
                txtPacketCount.Text = _packetCount.ToString();
                txtStatusMessage.Text = data.ToString();

                // Update dock windows with new data
                _chartsWindow?.AddDataPoint(data.Timestamp,data.Ph,data.Tds,data.Temperature,data.Conductivity);
                _dataGridWindow?.AddData(data);
                _controlsWindow?.UpdateLatestData(data);
            });
        }

        private void OnConnectionStatusChanged(object? sender, string status)
        {
            Dispatcher.Invoke(() =>
            {
                txtStatusMessage.Text = status;
            });
        }

        private void OnErrorOccurred(object? sender, Exception ex)
        {
            Dispatcher.Invoke(() =>
            {
                txtStatusMessage.Text = $"Error: {ex.Message}";
            });
        }

        private void Window_Closing(object sender, System.ComponentModel.CancelEventArgs e)
        {
            _tcpClient?.Dispose();
        }
    }
}