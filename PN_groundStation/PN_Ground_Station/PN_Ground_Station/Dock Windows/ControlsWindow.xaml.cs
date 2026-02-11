using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Data;
using System.Windows.Documents;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Media.Imaging;
using System.Windows.Navigation;
using System.Windows.Shapes;

namespace PN_Ground_Station.DockWindows
{
    /// <summary>
    /// Logika interakcji dla klasy ControlsWindow.xaml
    /// </summary>
    public partial class ControlsWindow : UserControl
    {
        private readonly TcpDataClient _tcpClient;
        public ControlsWindow(TcpDataClient _tcpClient)
        {
            InitializeComponent();
            this._tcpClient = _tcpClient;
            _tcpClient = new TcpDataClient();
            
        }

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

        private void BtnStartPump_Click(object sender, RoutedEventArgs e)
        {
            MessageBox.Show("Pump control not implemented yet.\nThis feature is under development.",
                "Not Implemented", MessageBoxButton.OK, MessageBoxImage.Information);
        }

        private void BtnStopPump_Click(object sender, RoutedEventArgs e)
        {
            MessageBox.Show("Pump control not implemented yet.\nThis feature is under development.",
                "Not Implemented", MessageBoxButton.OK, MessageBoxImage.Information);
        }

        private void BtnStartCycle_Click(object sender, RoutedEventArgs e)
        {
            MessageBox.Show("Measurement cycle not implemented yet.\nThis feature is under development.",
                "Not Implemented", MessageBoxButton.OK, MessageBoxImage.Information);
        }

        private void ScrollViewer_PreviewMouseWheel(object sender, MouseWheelEventArgs e)
        {
            ScrollViewer scrollViewer = (ScrollViewer)sender;

            // Zmniejsz czułość - podziel Delta przez większą wartość
            double scrollAmount = e.Delta / 3.0; // standardowo Delta to około 120

            scrollViewer.ScrollToVerticalOffset(scrollViewer.VerticalOffset - scrollAmount);

            e.Handled = true; // Zapobiega domyślnemu scrollowaniu
        }

        private async void btnMeasure_Click(object sender, RoutedEventArgs e)
        {
            await _tcpClient.SendCommandAsync("measure",120,0);
        }
    }
}
