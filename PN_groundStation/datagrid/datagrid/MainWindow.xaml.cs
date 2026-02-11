using System.Collections.ObjectModel;
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

namespace datagrid
{
    
    /// <summary>
    /// Interaction logic for MainWindow.xaml
    /// </summary>
    public partial class MainWindow : Window
    {
        public ObservableCollection<Osoba> osoby { get; } = new ObservableCollection<Osoba>();
        
        public MainWindow()
        {
            
            InitializeComponent();
            DataContext = this;
            osoby.Add(new Osoba {imie="Jan",nazwisko="Kazimierz",wiek=18});
            osoby.Add(new Osoba {imie="Radosław",nazwisko="Kazimierz",wiek=19});
        }

        private void Button_Click(object sender, RoutedEventArgs e)
        {

        }

        private void Button_Click_1(object sender, RoutedEventArgs e)
        {

        }
    }
}