using System;
using System.Windows.Controls;
using LiveCharts;
using LiveCharts.Defaults;
using LiveCharts.Wpf;

namespace PN_Ground_Station.DockWindows
{
    public partial class ChartsWindow : UserControl
    {
        public SeriesCollection PhSeries { get; set; }
        public SeriesCollection TdsSeries { get; set; }
        public SeriesCollection TempSeries { get; set; }
        public SeriesCollection CondSeries { get; set; }

        public ChartsWindow()
        {
            InitializeComponent();
            DataContext = this;

            // Initialize pH Series
            PhSeries = new SeriesCollection
            {
                new LineSeries
                {
                    Title = "pH",
                    Values = new ChartValues<ObservablePoint>(),
                    PointGeometrySize = 8,
                    Fill = System.Windows.Media.Brushes.Transparent
                }
            };

            // Initialize TDS Series
            TdsSeries = new SeriesCollection
            {
                new LineSeries
                {
                    Title = "TDS",
                    Values = new ChartValues<ObservablePoint>(),
                    PointGeometrySize = 8,
                    Fill = System.Windows.Media.Brushes.Transparent
                }
            };

            // Initialize Temperature Series
            TempSeries = new SeriesCollection
            {
                new LineSeries
                {
                    Title = "Temperature",
                    Values = new ChartValues<ObservablePoint>(),
                    PointGeometrySize = 8,
                    Fill = System.Windows.Media.Brushes.Transparent
                }
            };

            // Initialize Conductivity Series
            CondSeries = new SeriesCollection
            {
                new LineSeries
                {
                    Title = "Conductivity",
                    Values = new ChartValues<ObservablePoint>(),
                    PointGeometrySize = 8,
                    Fill = System.Windows.Media.Brushes.Transparent
                }
            };
        }

        // Przykładowa metoda do dodawania danych
        public void AddDataPoint(double time, double ph, double tds, double temp, double cond)
        {
            PhSeries[0].Values.Add(new ObservablePoint(time, ph));
            TdsSeries[0].Values.Add(new ObservablePoint(time, tds));
            TempSeries[0].Values.Add(new ObservablePoint(time, temp));
            CondSeries[0].Values.Add(new ObservablePoint(time, cond));
        }
    }
}