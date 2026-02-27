using System;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Input;

namespace PN_Ground_Station.DockWindows
{
    public partial class ControlsWindow : UserControl
    {
        private readonly TcpDataClient _tcpClient;
        private readonly BoatController _boat;

        public ControlsWindow(TcpDataClient tcpClient)
        {
            InitializeComponent();
            _tcpClient = tcpClient;                 
            _boat = new BoatController(_tcpClient);

            // Klawiatura — UserControl musi być focusable
            this.Focusable = true;
            this.KeyDown += _boat.OnKeyDown;
            this.KeyUp += _boat.OnKeyUp;

            // aktywuje klawiaturę
            this.MouseDown += (s, e) => this.Focus();
        }

        // ── Czujniki ─────────────────────────────────────────────────────────

        public void UpdateLatestData(SensorData data)
        {
            txtPh.Text = data.Ph.ToString("F2");
            txtPhStatus.Text = data.GetPhStatus();
            txtTds.Text = data.Tds.ToString("F1");
            txtTdsUnit.Text = "ppm";
            txtTemp.Text = data.Temperature.ToString("F1");
            txtTempUnit.Text = "°C";
            txtCond.Text = data.Conductivity.ToString("F0");
            txtCondUnit.Text = "µS/cm";
            txtBattery.Text = data.BatteryVoltage.ToString("F2");
            txtBatteryUnit.Text = "V";
            txtQuality.Text = data.GetWaterQuality();
        }

        // ── Pompy / Pomiary ───────────────────────────────────────────────────

        private async void BtnStartPump_Click(object sender, RoutedEventArgs e)
            => await _tcpClient.SendCommandAsync("pump_on", 0, 0);

        private async void BtnStopPump_Click(object sender, RoutedEventArgs e)
            => await _tcpClient.SendCommandAsync("pump_off", 0, 0);

        private async void BtnStartLoadingCycle_Click(object sender, RoutedEventArgs e)
            => await _tcpClient.SendCommandAsync("samples_loading", 0, 0);

        private async void btnStartMeasurementCycle_Click(object sender, RoutedEventArgs e)
            => await _tcpClient.SendCommandAsync("measure", 120, 0);

        private async void btnStartRejectingCycle_Click(object sender, RoutedEventArgs e)
            => await _tcpClient.SendCommandAsync("reject_sample", 0, 0);

        // ── Sterowanie łódką ─────────────────────────────────────────────────

        private void BtnBoatToggle_Click(object sender, RoutedEventArgs e)
        {
            if (_boat.IsActive)
            {
                _boat.Deactivate();
                btnBoatToggle.Content = "▶  Activate WSAD Control";
                btnBoatToggle.Background = System.Windows.Media.Brushes.DarkRed;
                txtBoatStatus.Text = "● INACTIVE";
                txtBoatStatus.Foreground = System.Windows.Media.Brushes.OrangeRed;
            }
            else
            {
                _boat.Activate();
                this.Focus();  // Daj focus żeby klawiatura działała od razu
                btnBoatToggle.Content = "⏹  Deactivate WSAD Control";
                btnBoatToggle.Background = System.Windows.Media.Brushes.DarkGreen;
                txtBoatStatus.Text = "● ACTIVE — use WSAD to steer";
                txtBoatStatus.Foreground = System.Windows.Media.Brushes.LimeGreen;
            }
        }

        // ── Scroll ───────────────────────────────────────────────────────────

        private void ScrollViewer_PreviewMouseWheel(object sender, MouseWheelEventArgs e)
        {
            var scrollViewer = (ScrollViewer)sender;
            scrollViewer.ScrollToVerticalOffset(scrollViewer.VerticalOffset - e.Delta / 3.0);
            e.Handled = true;
        }
    }
}