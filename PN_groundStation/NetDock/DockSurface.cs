using System;
using System.Collections.Generic;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace NetDock
{
    /// <summary>
    /// Main docking surface - holds all dockable items with Grid-based layout
    /// Standalone version - NO XAML required
    /// </summary>
    public class DockSurface : Grid
    {
        private readonly Dictionary<DockDirection, Grid> _regions = new Dictionary<DockDirection, Grid>();

        public DockSurface()
        {
            InitializeLayout();
        }

        private void InitializeLayout()
        {
            // Clear existing definitions
            this.ColumnDefinitions.Clear();
            this.RowDefinitions.Clear();
            this.Children.Clear();

            // Create 2x2 grid layout with splitters
            // Columns: [Panel] [Splitter] [Panel]
            this.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(1, GridUnitType.Star) });
            this.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(5) }); // Splitter
            this.ColumnDefinitions.Add(new ColumnDefinition { Width = new GridLength(2, GridUnitType.Star) });

            // Rows: [Panel] [Splitter] [Panel]
            this.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });
            this.RowDefinitions.Add(new RowDefinition { Height = new GridLength(5) }); // Splitter
            this.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

            // Create 4 regions (Top-Left, Top-Right, Bottom-Left, Bottom-Right)
            CreateRegion(DockDirection.Left, 0, 0);      // Top-Left
            CreateRegion(DockDirection.Top, 0, 2);       // Top-Right
            CreateRegion(DockDirection.Bottom, 2, 0);    // Bottom-Left
            CreateRegion(DockDirection.Right, 2, 2);     // Bottom-Right

            // Add vertical splitter (between left and right columns)
            var verticalSplitter = new GridSplitter
            {
                Width = 5,
                HorizontalAlignment = HorizontalAlignment.Stretch,
                VerticalAlignment = VerticalAlignment.Stretch,
                Background = new SolidColorBrush(Color.FromRgb(0x3F, 0x3F, 0x46)),
                ShowsPreview = false
            };
            Grid.SetColumn(verticalSplitter, 1);
            Grid.SetRowSpan(verticalSplitter, 3);
            this.Children.Add(verticalSplitter);

            // Add horizontal splitter for left column (between top and bottom)
            var horizontalSplitterLeft = new GridSplitter
            {
                Height = 5,
                HorizontalAlignment = HorizontalAlignment.Stretch,
                VerticalAlignment = VerticalAlignment.Stretch,
                Background = new SolidColorBrush(Color.FromRgb(0x3F, 0x3F, 0x46)),
                ShowsPreview = false
            };
            Grid.SetColumn(horizontalSplitterLeft, 0);
            Grid.SetRow(horizontalSplitterLeft, 1);
            this.Children.Add(horizontalSplitterLeft);

            // Add horizontal splitter for right column (between top and bottom)
            var horizontalSplitterRight = new GridSplitter
            {
                Height = 5,
                HorizontalAlignment = HorizontalAlignment.Stretch,
                VerticalAlignment = VerticalAlignment.Stretch,
                Background = new SolidColorBrush(Color.FromRgb(0x3F, 0x3F, 0x46)),
                ShowsPreview = false
            };
            Grid.SetColumn(horizontalSplitterRight, 2);
            Grid.SetRow(horizontalSplitterRight, 1);
            this.Children.Add(horizontalSplitterRight);
        }

        private void CreateRegion(DockDirection direction, int row, int column)
        {
            var region = new Grid
            {
                Background = new SolidColorBrush(Color.FromRgb(0x1E, 0x1E, 0x1E))
            };

            Grid.SetRow(region, row);
            Grid.SetColumn(region, column);
            this.Children.Add(region);

            _regions[direction] = region;
        }

        /// <summary>
        /// Add a dock item to the surface
        /// </summary>
        public void Add(DockItem item, DockDirection direction = DockDirection.Center)
        {
            if (item == null)
                throw new ArgumentNullException(nameof(item));

            System.Diagnostics.Debug.WriteLine($"DockSurface.Add: {item.TabName} to {direction}");

            // Get the target region
            Grid targetRegion;
            if (!_regions.TryGetValue(direction, out targetRegion))
            {
                System.Diagnostics.Debug.WriteLine($"Direction {direction} not found, using Left");
                targetRegion = _regions[DockDirection.Left];
            }

            // Create container with header and content
            var container = CreateContainer(item);

            // Add to region
            targetRegion.Children.Add(container);

            System.Diagnostics.Debug.WriteLine($"Added successfully. Region now has {targetRegion.Children.Count} children");
        }

        private Border CreateContainer(DockItem item)
        {
            // Main container border
            var border = new Border
            {
                Background = new SolidColorBrush(Color.FromRgb(0x25, 0x25, 0x26)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(0x3F, 0x3F, 0x46)),
                BorderThickness = new Thickness(1),
                Margin = new Thickness(5)
            };

            // Container grid (header + content)
            var containerGrid = new Grid();
            containerGrid.RowDefinitions.Add(new RowDefinition { Height = GridLength.Auto });
            containerGrid.RowDefinitions.Add(new RowDefinition { Height = new GridLength(1, GridUnitType.Star) });

            // Header
            var header = CreateHeader(item.TabName);
            Grid.SetRow(header, 0);
            containerGrid.Children.Add(header);

            // Content
            var contentBorder = new Border
            {
                Child = item.Content,
                Padding = new Thickness(0)
            };
            Grid.SetRow(contentBorder, 1);
            containerGrid.Children.Add(contentBorder);

            border.Child = containerGrid;
            return border;
        }

        private Border CreateHeader(string title)
        {
            var header = new Border
            {
                Background = new SolidColorBrush(Color.FromRgb(0x2D, 0x2D, 0x30)),
                BorderBrush = new SolidColorBrush(Color.FromRgb(0x3F, 0x3F, 0x46)),
                BorderThickness = new Thickness(0, 0, 0, 1),
                Padding = new Thickness(10, 8, 10, 8)
            };

            var headerText = new TextBlock
            {
                Text = title ?? "Untitled",
                Foreground = new SolidColorBrush(Color.FromRgb(0xCC, 0xCC, 0xCC)),
                FontWeight = FontWeights.Bold,
                FontSize = 14
            };

            header.Child = headerText;
            return header;
        }

        /// <summary>
        /// Clear all items from all regions
        /// </summary>
        public void Clear()
        {
            foreach (var region in _regions.Values)
            {
                region.Children.Clear();
            }
        }

        /// <summary>
        /// Get region by direction
        /// </summary>
        public Grid GetRegion(DockDirection direction)
        {
            return _regions.ContainsKey(direction) ? _regions[direction] : null;
        }
    }

    /// <summary>
    /// Direction for docking new items
    /// </summary>
    public enum DockDirection
    {
        Center,
        Left,
        Right,
        Top,
        Bottom
    }
}