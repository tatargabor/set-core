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
  // Handle deep link
  const slug = event.url.split('.app').pop();
  if (slug) router.push(slug);
});
```

## Custom Plugin Pattern

When built-in plugins aren't enough:

1. Create a Capacitor plugin package (or use local plugin)
2. Define the TypeScript interface
3. Implement native code in Swift (iOS) / Kotlin (Android)
4. Register in `capacitor.config.ts`

Prefer built-in or well-maintained community plugins over custom native code.

## App Groups (Share Extension)

When the app has a Share Extension, data flows through App Groups:

```
Share Extension → App Groups (UserDefaults) → Main App (Capacitor reads on resume)
```

- Write to App Groups in the Share Extension (native Swift)
- Read from App Groups in the main app via a custom Capacitor plugin or on `appStateChange`
- Always validate data read from App Groups before processing
