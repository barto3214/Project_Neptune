using System;
using System.Windows;

namespace NetDock
{
    /// <summary>
    /// Represents a dockable item (window/tab content)
    /// </summary>
    public class DockItem
    {
        /// <summary>
        /// Content to display in the dock item
        /// </summary>
        public UIElement Content { get; set; }

        /// <summary>
        /// Tab/Window title
        /// </summary>
        public string TabName { get; set; } = "Untitled";

        /// <summary>
        /// Can this item be closed?
        /// </summary>
        public bool CanClose { get; set; } = true;

        /// <summary>
        /// Can this item float as separate window?
        /// </summary>
        public bool CanFloat { get; set; } = true;

        public DockItem(UIElement content)
        {
            Content = content ?? throw new ArgumentNullException(nameof(content));
        }

        public DockItem(UIElement content, string tabName) : this(content)
        {
            TabName = tabName;
        }
    }
}