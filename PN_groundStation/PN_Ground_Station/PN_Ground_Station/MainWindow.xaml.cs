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
using NetDock; 
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

            // Initialize dock windows after component initialization
            Loaded += Window_Loaded;
            Closing += Window_Closing;
        }

        private void Window_Loaded(object sender, RoutedEventArgs e)
        {
            System.Diagnostics.Debug.WriteLine("=== Window_Loaded START ===");

            // Initialize dock windows
            InitializeDockWindows();

            txtStatusMessage.Text = "Ready. Configure connection and click Connect.";

            System.Diagnostics.Debug.WriteLine("=== Window_Loaded END ===");
        }

        private void InitializeDockWindows()
        {
            System.Diagnostics.Debug.WriteLine(">>> InitializeDockWindows START");

            try
            {
                // Create dock windows
                System.Diagnostics.Debug.WriteLine("Creating ChartsWindow...");
                _chartsWindow = new ChartsWindow();
                System.Diagnostics.Debug.WriteLine($"ChartsWindow created: {_chartsWindow != null}");

                System.Diagnostics.Debug.WriteLine("Creating DataGridWindow...");
                _dataGridWindow = new DataGridWindow();
                System.Diagnostics.Debug.WriteLine($"DataGridWindow created: {_dataGridWindow != null}");

                System.Diagnostics.Debug.WriteLine("Creating CameraWindow...");
                _cameraWindow = new CameraWindow();
                System.Diagnostics.Debug.WriteLine($"CameraWindow created: {_cameraWindow != null}");

                System.Diagnostics.Debug.WriteLine("Creating ControlsWindow...");
                _controlsWindow = new ControlsWindow(_tcpClient);
                System.Diagnostics.Debug.WriteLine($"ControlsWindow created: {_controlsWindow != null}");

                // Clear any existing content
                System.Diagnostics.Debug.WriteLine("Clearing dockSurface...");
                dockSurface.Clear();
                System.Diagnostics.Debug.WriteLine($"DockSurface children after Clear: {dockSurface.Children.Count}");

                // Create DockItems (using NetDock.DockItem, not NetDock.Controls.DockItem)
                System.Diagnostics.Debug.WriteLine("Adding Camera to Left...");
                var cameraItem = new NetDock.DockItem(_cameraWindow)
                {
                    TabName = "📷 Camera"
                };
                dockSurface.Add(cameraItem, NetDock.DockDirection.Left);
                System.Diagnostics.Debug.WriteLine($"DockSurface children after Camera: {dockSurface.Children.Count}");

                System.Diagnostics.Debug.WriteLine("Adding Charts to Top...");
                var chartsItem = new NetDock.DockItem(_chartsWindow)
                {
                    TabName = "📊 Charts"
                };
                dockSurface.Add(chartsItem, NetDock.DockDirection.Top);
                System.Diagnostics.Debug.WriteLine($"DockSurface children after Charts: {dockSurface.Children.Count}");

                System.Diagnostics.Debug.WriteLine("Adding Controls to Bottom...");
                var controlsItem = new NetDock.DockItem(_controlsWindow)
                {
                    TabName = "⚙️ Controls"
                };
                dockSurface.Add(controlsItem, NetDock.DockDirection.Bottom);
                System.Diagnostics.Debug.WriteLine($"DockSurface children after Controls: {dockSurface.Children.Count}");

                System.Diagnostics.Debug.WriteLine("Adding DataGrid to Right...");
                var dataGridItem = new NetDock.DockItem(_dataGridWindow)
                {
                    TabName = "📜 Data History"
                };
                dockSurface.Add(dataGridItem, NetDock.DockDirection.Right);
                System.Diagnostics.Debug.WriteLine($"DockSurface children after DataGrid: {dockSurface.Children.Count}");

                System.Diagnostics.Debug.WriteLine(">>> InitializeDockWindows SUCCESS");
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($">>> InitializeDockWindows ERROR: {ex.Message}");
                System.Diagnostics.Debug.WriteLine($"Stack trace: {ex.StackTrace}");
                MessageBox.Show($"Error initializing windows:\n{ex.Message}", "Error",
                    MessageBoxButton.OK, MessageBoxImage.Error);
            }
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

                await _tcpClient.ConnectAsync(host,port);

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

                // Keep only last 50 records for charts
                if (_dataHistory.Count > 50)
                    _dataHistory.RemoveAt(0);

                // Update status bar
                txtLastDataTime.Text = data.ReceivedAt.ToString("HH:mm:ss");
                txtPacketCount.Text = _packetCount.ToString();
                txtStatusMessage.Text = data.ToString();

                // Update dock windows with new data
                _chartsWindow?.AddDataPoint(data.Timestamp, data.Ph, data.Tds, data.Temperature, data.Conductivity);
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
                System.Diagnostics.Debug.WriteLine($"TCP Error: {ex.Message}");
            });
        }

        private void Window_Closing(object sender, System.ComponentModel.CancelEventArgs e)
        {
            _tcpClient?.Dispose();
        }

        private void btnAbout_Click(object sender, RoutedEventArgs e)
        {
            AboutMe aboutWindow = new AboutMe();
            aboutWindow.Owner = this;
            aboutWindow.ShowDialog();
        }

        private void btnSettings_Click(object sender, RoutedEventArgs e)
        {

        }
    }
}