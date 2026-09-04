using Microsoft.Xna.Framework;
using Portico.Dashboard;
using Roci.Display;
using Roci.Hosting.MonoGame;
using Roci.Input;
using Roci.Launch;
using Roci.Rendering;
using Roci.Rendering.FontStashSharp;
using Roci.Rendering.MonoGame;
using Roci.Ui;
using Roci.Ui.Input;
using Roci.Ui.Rendering;
using LiveInputProvider = Roci.Input.MonoGame.MonoGameInputProvider;

namespace Portico.App;

/// <summary>Hosts the retained Roci dashboard in a desktop MonoGame window.</summary>
public sealed class PorticoDashboardGame : HostedMonoGameGame
{
    /// <summary>Logical width of the normal desktop dashboard window.</summary>
    public const int DefaultWidth = 1280;

    /// <summary>Logical height of the normal desktop dashboard window.</summary>
    public const int DefaultHeight = 820;

    private readonly IInputProvider _inputProvider;
    private readonly InputManager _inputHandler;
    private readonly UiInputMap _uiInputMap;

    private MonoGameRenderScope _rendering = null!;
    private Renderer2D _renderer = null!;
    private Roci.Core.ITextMeasurer _textMeasurer = null!;
    private PorticoDashboardScene _scene = null!;
    private UiRenderPass _uiRenderPass = null!;
    private UiPhysicalViewport _uiViewport;
    private UiRenderScaleOptions _uiScaleOptions;

    /// <summary>Creates a live desktop dashboard for an already loaded session.</summary>
    public PorticoDashboardGame(DashboardSession session)
        : base(GameRunContext.Empty, CreateHostSettings())
    {
        ArgumentNullException.ThrowIfNull(session);

        Content.RootDirectory = "Content";
        Session = session;
        _inputHandler = new InputManager(CreateInputConfig(), new InputContextId("ui"));
        _inputProvider = Presentation.WrapInput(new LiveInputProvider());
        _uiInputMap = UiInputMap.Default();
    }

    /// <summary>Gets the application session rendered by this game.</summary>
    public DashboardSession Session { get; }

    /// <summary>Creates the standard desktop host settings used by the CLI.</summary>
    public static MonoGameHostSettings CreateHostSettings()
        => new()
        {
            LogicalSize = new DisplaySize(DefaultWidth, DefaultHeight),
            Title = "Portico",
            ViewportScaleMode = ViewportScaleMode.Fit,
            SamplerMode = SamplerMode.Linear
        };

    /// <inheritdoc />
    protected override void LoadContent()
    {
        _rendering = MonoGameRenderScope.Create(
            GraphicsDevice,
            static device => FontStashTextRenderer.CreateWithDefaultFonts(device));
        _renderer = _rendering.Renderer;
        _textMeasurer = _rendering.TextMeasurer!;

        RefreshUiViewport();
        _scene = new PorticoDashboardScene(_uiViewport.LogicalSize, Session);
        _scene.Stage.SetCommandConfig(_uiInputMap.CreateCommandConfig());
        _uiRenderPass = new UiRenderPass(
            _scene.Stage,
            _renderer,
            _textMeasurer,
            UiTextureResolvers.Empty);
    }

    /// <inheritdoc />
    protected override void StepFrame(float deltaSeconds)
    {
        RefreshUiViewport();
        _scene.Stage.Resize(_uiViewport.LogicalSize);

        InputState state = _inputProvider.CaptureState();
        _inputHandler.Update(state);
        UiInput input = _inputHandler.ReadUiInput(_uiInputMap, 0, deltaSeconds);
        _scene.Update(ref input, _textMeasurer, _uiScaleOptions, _uiViewport.EffectiveUIScale);
    }

    /// <inheritdoc />
    protected override void DrawFrame(GameTime gameTime)
    {
        _renderer.SetRenderTarget(null);
        _renderer.Clear(Roci.Core.Color.Black);

        BatchConfig batchConfig = _uiRenderPass.CreateViewportBatchConfig(
            BatchConfig.Default,
            _uiViewport,
            UiRenderTargetSpace.CurrentTarget,
            _uiScaleOptions);
        _uiRenderPass.RenderPreparedBatch(
            batchConfig,
            _uiScaleOptions,
            _uiViewport.EffectiveUIScale);
    }

    /// <inheritdoc />
    protected override void UnloadContent()
    {
        base.UnloadContent();
        _rendering?.Dispose();
    }

    private void RefreshUiViewport()
    {
        ViewportResult viewport = Presentation.Display.CurrentViewport;
        _uiViewport = new UiPhysicalViewport(viewport.Bounds, viewport.Scale);
        _uiScaleOptions = _uiViewport.EffectiveUIScale > 1f
            ? UiRenderScaleOptions.CrispText
            : UiRenderScaleOptions.Default;
    }

    private static InputConfig CreateInputConfig()
        => new InputConfigBuilder()
            .Context(new InputContextId("ui"))
                .Bind(InputCommands.MoveCursor, "Mouse.MoveCursor")
                .Bind(InputCommands.ClickLeft, "Mouse.ClickLeft")
                .Bind(InputCommands.ClickRight, "Mouse.ClickRight")
                .Bind(InputCommands.ScrollVertical, "Mouse.ScrollVertical")
                .Bind(InputCommands.ScrollHorizontal, "Mouse.ScrollHorizontal")
                .Bind(InputCommands.Accept, "Key.Enter", "Key.Space", "GamePad.South")
                .Bind(InputCommands.Cancel, "Key.Escape", "GamePad.East")
                .Bind(InputCommands.Next, "Key.Tab")
                .Bind(InputCommands.Previous, "Key.LeftShift", "GamePad.LeftBumper")
                .Bind(InputCommands.Up, "Key.Up", "Key.W", "GamePad.DPadUp")
                .Bind(InputCommands.Down, "Key.Down", "Key.S", "GamePad.DPadDown")
                .Bind(InputCommands.Left, "Key.Left", "Key.A", "GamePad.DPadLeft")
                .Bind(InputCommands.Right, "Key.Right", "Key.D", "GamePad.DPadRight")
            .Build();
}
