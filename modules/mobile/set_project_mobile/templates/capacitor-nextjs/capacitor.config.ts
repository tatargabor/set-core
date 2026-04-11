import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.example.app',
  appName: 'MyApp',
  webDir: 'out',
  server: {
    // During development, use the Next.js dev server
    // url: 'http://localhost:3000',
    // cleartext: true,
  },
  plugins: {
    // Configure Capacitor plugins here
  },
};

export default config;
