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
        public ControlsWindow()
        {
            InitializeComponent();
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
    }
}
