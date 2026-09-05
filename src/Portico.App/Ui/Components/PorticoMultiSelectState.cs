namespace Portico.App.Ui.Components;

/// <summary>Holds the local interaction state for one composed multi-select.</summary>
public sealed class PorticoMultiSelectState<T>
    where T : notnull
{
    private readonly HashSet<T> _selected;

    /// <summary>Creates an initially closed multi-select with optional selected values.</summary>
    public PorticoMultiSelectState(IEnumerable<T>? selected = null, IEqualityComparer<T>? comparer = null)
    {
        _selected = new HashSet<T>(selected ?? [], comparer ?? EqualityComparer<T>.Default);
    }

    /// <summary>Gets whether the popover is open.</summary>
    public bool IsOpen { get; private set; }

    /// <summary>Gets the current selected values.</summary>
    public IReadOnlySet<T> SelectedValues => _selected;

    /// <summary>Gets or sets the text used to filter a long option list.</summary>
    public string SearchText { get; private set; } = string.Empty;

    /// <summary>Changes the retained popover state.</summary>
    public bool SetOpen(bool isOpen)
    {
        if (IsOpen == isOpen)
            return false;
        IsOpen = isOpen;
        return true;
    }

    /// <summary>Replaces the retained selection without raising a page callback.</summary>
    public void ReplaceSelection(IEnumerable<T> values)
    {
        ArgumentNullException.ThrowIfNull(values);
        if (ReferenceEquals(values, _selected))
            return;
        _selected.Clear();
        _selected.UnionWith(values);
    }

    /// <summary>Changes one item and raises the supplied callback once when it changed.</summary>
    public bool SetSelected(T value, bool selected, Action<IReadOnlySet<T>>? onChanged = null)
    {
        bool changed = selected ? _selected.Add(value) : _selected.Remove(value);
        if (changed)
            onChanged?.Invoke(new HashSet<T>(_selected, _selected.Comparer));
        return changed;
    }

    /// <summary>Clears the retained selection and raises the supplied callback once when needed.</summary>
    public bool Clear(Action<IReadOnlySet<T>>? onChanged = null)
    {
        if (_selected.Count == 0)
            return false;
        _selected.Clear();
        onChanged?.Invoke(new HashSet<T>(_selected, _selected.Comparer));
        return true;
    }

    /// <summary>Changes the retained search text without changing selected values.</summary>
    public bool SetSearchText(string? value)
    {
        string normalized = value?.Trim() ?? string.Empty;
        if (string.Equals(SearchText, normalized, StringComparison.Ordinal))
            return false;
        SearchText = normalized;
        return true;
    }

    /// <summary>Checks whether an item label matches the current search text.</summary>
    public bool Matches(string label)
        => string.IsNullOrWhiteSpace(SearchText)
            || label.Contains(SearchText, StringComparison.OrdinalIgnoreCase);
}

/// <summary>Defines one visible multi-select choice.</summary>
public sealed record PorticoMultiSelectItem<T>(string Id, T Value, string Label)
    where T : notnull;
