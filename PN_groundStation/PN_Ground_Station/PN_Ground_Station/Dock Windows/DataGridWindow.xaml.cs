using System;
using System.Collections.Generic;
using System.Collections.ObjectModel;
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
    /// Logika interakcji dla klasy DataGridWindow.xaml
    /// </summary>
    public partial class DataGridWindow : UserControl
    {
        public ObservableCollection<SensorData> DataHistory { get; } = new();

        public DataGridWindow()
        {
            InitializeComponent();
            DataContext = this;
        }

        public void AddData(SensorData data)
        {
            // Insert at beginning
            DataHistory.Insert(0, data);

            // Keep only last 100
            if (DataHistory.Count > 100)
                DataHistory.RemoveAt(DataHistory.Count - 1);
        }

        public void ClearData()
        {
            DataHistory.Clear();
        }
    }
}
