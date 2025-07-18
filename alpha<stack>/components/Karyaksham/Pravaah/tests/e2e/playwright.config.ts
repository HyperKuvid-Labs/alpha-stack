import { defineConfig, devices } from '@playwright/test';

/**
 * See https://playwright.dev/docs/test-configuration.
 */
export default defineConfig({
  testDir: './specs',
  /* Run tests in files in parallel */
  fullyParallel: true,
  /* Fail the build on CI if you accidentally left test.only in the source code. */
  forbidOnly: !!process.env.CI,
  /* Retry on CI only */
  retries: process.env.CI ? 2 : 0,
  /* Opt out of parallel tests on CI. */
  workers: process.env.CI ? 1 : undefined,
  /* Reporter to use. See https://playwright.dev/docs/test-reporters */
  reporter: process.env.CI ? 'github' : [['list'], ['html', { open: 'never' }]],

  /* Shared settings for all the projects below. See https://playwright.dev/docs/api/class-testoptions. */
  use: {
    /* Base URL to use in tests against the frontend application. */
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',

    /* Collect trace when retrying the first time. See https://playwright.dev/docs/trace-viewer */
    trace: 'on-first-retry',

    /* Configure default viewport for tests to simulate a common desktop resolution */
    viewport: { width: 1280, height: 720 },

    /* Timeout for each Playwright action (e.g., click, type, fill) in milliseconds */
    actionTimeout: 10 * 1000, // 10 seconds

    /* Timeout for page navigations (e.g., page.goto, page.click triggering navigation) in milliseconds */
    navigationTimeout: 30 * 1000, // 30 seconds
  },

  /* Configure projects for major browsers */
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
    {
      name: 'firefox',
      use: { ...devices['Desktop Firefox'] },
    },
    {
      name: 'webkit',
      use: { ...devices['Desktop Safari'] },
    },

    /* Example of testing against mobile viewports (uncomment as needed) */
    // {
    //   name: 'Mobile Chrome',
    //   use: { ...devices['Pixel 5'] },
    // },
    // {
    //   name: 'Mobile Safari',
    //   use: { ...devices['iPhone 12'] },
    // },
  ],

  /* Run your local dev server before starting the tests. This ensures the frontend is available. */
  webServer: {
    /**
     * Command to start the frontend development server.
     * Assumes 'npm run dev' is defined in frontend/package.json
     * 'cwd' (current working directory) is set relative to this config file.
     * This config is in karyaksham/tests/e2e/, and frontend is in karyaksham/frontend/.
     */
    command: 'npm run dev',
    url: 'http://localhost:3000', // URL the frontend dev server is expected to listen on
    reuseExistingServer: !process.env.CI, // Do not reuse server on CI to ensure a clean state for each build
    timeout: 120 * 1000, // Give the server up to 2 minutes to start
    stdout: 'pipe', // Pipe stdout for debugging purposes
    stderr: 'pipe', // Pipe stderr for debugging purposes
    cwd: '../../frontend', // Change directory to frontend before running the command
  },
});