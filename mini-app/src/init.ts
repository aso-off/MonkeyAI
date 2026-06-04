import {
  setDebug,
  themeParams,
  initData,
  viewport,
  init as initSDK,
  mockTelegramEnv,
  retrieveLaunchParams,
  emitEvent,
  miniApp,
  backButton,
  settingsButton,
  swipeBehavior,
} from '@tma.js/sdk-vue';

/**
 * Initializes the application and configures its dependencies.
 */
export async function init(options: {
  debug: boolean;
  eruda: boolean;
  mockForMacOS: boolean;
}): Promise<void> {
  // Set @telegram-apps/sdk-vue debug mode and initialize it.
  setDebug(options.debug);
  initSDK();

  // Add Eruda if needed (debug mode only).
  if (options.eruda) {
    import('eruda').then(({ default: eruda }) => {
      eruda.init();
      eruda.position({ x: window.innerWidth - 50, y: 0 });
    });
  }

  // Telegram for macOS has a ton of bugs, including cases, when the client doesn't
  // even response to the "web_app_request_theme" method. It also generates an incorrect
  // event for the "web_app_request_safe_area" method.
  if (options.mockForMacOS) {
    let firstThemeSent = false;
    mockTelegramEnv({
      onEvent(event, next) {
        if (event.name === 'web_app_request_theme') {
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          let tp: any = {};
          if (firstThemeSent) {
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            tp = themeParams.state() as any;
          } else {
            firstThemeSent = true;
            // eslint-disable-next-line @typescript-eslint/no-explicit-any
            tp = (retrieveLaunchParams().tgWebAppThemeParams ?? {}) as any;
          }
          // eslint-disable-next-line @typescript-eslint/no-explicit-any
          return emitEvent('theme_changed', { theme_params: tp } as any);
        }

        if (event.name === 'web_app_request_safe_area') {
          return emitEvent('safe_area_changed', { left: 0, top: 0, right: 0, bottom: 0 });
        }

        next();
      },
    });
  }

  // Mount all components used in the project.
  backButton.mount.ifAvailable();
  settingsButton.mount.ifAvailable();
  initData.restore();

  if (miniApp.mount.isAvailable()) {
    themeParams.mount();
    miniApp.mount();
    themeParams.bindCssVars();
  }

  if (viewport.mount.isAvailable()) {
    viewport.mount().then(() => {
      viewport.bindCssVars();
      // Expand to the maximum available height immediately. Without this the layout
      // viewport can start shorter than the screen, so the position:fixed footer floats
      // a few px above the device nav bar until the viewport settles on its own.
      viewport.expand.ifAvailable();
    });
  }

  // Disable vertical swipes (Telegram Mini Apps v7.7+). This is the officially
  // recommended fix for the "collapse / flicker on minimise & reopen" behaviour: it stops
  // the BottomSheet from reacting to in-content vertical drags, which keeps the viewport
  // stable and avoids the repaint glitch when the app is expanded back from the dock.
  if (swipeBehavior.mount.isAvailable()) {
    swipeBehavior.mount();
    swipeBehavior.disableVertical.ifAvailable();
  }
}