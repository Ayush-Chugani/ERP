import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  test: {
    maxWorkers: 1,
    environment: 'jsdom',
    include: ['tests/zz-live.test.tsx'],
    setupFiles: ['./tests/ui-setup.ts'],
    testTimeout: 120000,
  },
});
