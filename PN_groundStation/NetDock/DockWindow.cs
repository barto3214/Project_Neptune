using System;
using System.Windows;

namespace NetDock
{
    /// <summary>
    /// Floating window that hosts a DockItem
    /// </summary>
    public class DockWindow : Window
    {
        public DockItem DockItem { get; }

        public DockWindow(DockItem dockItem)
        {
            DockItem = dockItem ?? throw new ArgumentNullException(nameof(dockItem));

            Title = dockItem.TabName;
            Content = dockItem.Content;

            Width = 800;
            Height = 600;
            WindowStartupLocation = WindowStartupLocation.CenterScreen;
        }
    }
}