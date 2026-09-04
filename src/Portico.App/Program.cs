namespace Portico.App;

/// <summary>Starts the command-line and desktop entry points from an STA thread.</summary>
public static class Program
{
    /// <summary>Runs Portico and returns its stable process exit code.</summary>
    [STAThread]
    public static Task<int> Main(string[] args)
        => PorticoCli.RunAsync(args, Console.Out, Console.Error);
}
