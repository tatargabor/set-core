# Native Bridge Patterns

## Capacitor Plugin Bridge

Communication between web and native code flows through Capacitor's plugin system:

```
Web (TypeScript) → Capacitor Bridge → Native (Swift/Kotlin)
```

### Web → Native

```typescript
import { Preferences } from '@capacitor/preferences';

// Simple key-value storage (native implementation)
await Preferences.set({ key: 'token', value: 'abc123' });
const { value } = await Preferences.get({ key: 'token' });
```

### Native → Web (Events)

```typescript
import { App } from '@capacitor/app';

// Listen for native events
App.addListener('appUrlOpen', (event) => {
  const slug = event.url.split('.app').pop();
  if (slug) router.push(slug);
});
```

### Native → Web (JavaScript Injection)

AppDelegate can inject data into the WebView via JavaScript evaluation:

```swift
// Encode data as base64 to avoid JSON escaping issues
let jsonData = try JSONSerialization.data(withJSONObject: result)
let base64 = jsonData.base64EncodedString()
webView.evaluateJavaScript("window.handleNativeResult('\(base64)')")
```

Web side receives and decodes:
```typescript
window.handleNativeResult = (base64: string) => {
  const json = JSON.parse(atob(base64));
  // Process the result
};
```

Always use base64 encoding when passing structured data through JS evaluation — raw JSON with special characters will break.

## Device Identity Pattern

Mobile apps often use device-based identity instead of traditional login:

1. **Generate UUID** on first launch → store in Capacitor `Preferences`
2. **Sync to App Groups** (if Share Extension exists) → AppDelegate writes to shared `UserDefaults`
3. **Send to server** via header (`X-Device-Id`) or cookie
4. **Server validates** device status (pending/active/blocked)

```typescript
// Dual-mode: native Preferences on device, localStorage on web
export async function getDeviceId(): Promise<string> {
  if (Capacitor.isNativePlatform()) {
    const { value } = await Preferences.get({ key: 'device-id' });
    return value ?? await createAndStoreDeviceId();
  }
  return localStorage.getItem('device-id') ?? createAndStoreDeviceId();
}
```

## Share Extension Flow

```
Share Sheet → Share Extension → App Groups → Main App → Process
```

1. **User shares** content (URL, text, image) via iOS share sheet
2. **Share Extension** receives content, optionally calls backend API for extraction
3. **Extension stores** result in App Groups (`UserDefaults(suiteName: "group.xxx")`)
4. **Extension opens** main app via custom URL scheme (`myapp://shared?source=extension`)
5. **AppDelegate** detects on `applicationDidBecomeActive` or URL open
6. **AppDelegate reads** App Groups data, injects into WebView
7. **Web layer** processes the shared content

### Extension Constraints

- **25-second timeout** — if the extension takes too long, iOS kills it
- **Limited memory** — extensions get ~120MB max
- **No background execution** — use the main app for long-running tasks
- **Separate binary** — cannot import main app Swift modules directly

## Custom Plugin Pattern

When built-in plugins aren't enough:

1. Create a Capacitor plugin package (or use local plugin)
2. Define the TypeScript interface
3. Implement native code in Swift (iOS) / Kotlin (Android)
4. Register in `capacitor.config.ts`

Prefer built-in or well-maintained community plugins over custom native code.
