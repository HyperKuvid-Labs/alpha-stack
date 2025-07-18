import { test, expect, Page } from '@playwright/test';
import path from 'path';
import fs from 'fs';

// Helper function to generate a unique identifier for test users/jobs
const generateUniqueId = () => Math.random().toString(36).substring(2, 10);

test.describe('Job Submission and Monitoring E2E Flow', () => {
    let page: Page;
    let uniqueId: string;
    let testUsername: string;
    const testPassword = 'TestPassword123!';
    let dummyInputFilePath: string;

    test.beforeAll(() => {
        // Create a dummy CSV file for upload before all tests
        // This simulates a static fixture file being available.
        const fixtureDir = path.join(__dirname, '..', 'fixtures');
        if (!fs.existsSync(fixtureDir)) {
            fs.mkdirSync(fixtureDir, { recursive: true });
        }
        dummyInputFilePath = path.join(fixtureDir, 'sample_input.csv');
        const csvContent = `Name,Age,Country\nAlice,30,USA\nBob,24,India\nCharlie,35,UK\nDavid,29,India`;
        fs.writeFileSync(dummyInputFilePath, csvContent);
    });

    test.afterAll(() => {
        // Clean up the dummy CSV file after all tests
        if (fs.existsSync(dummyInputFilePath)) {
            fs.unlinkSync(dummyInputFilePath);
        }
    });

    test.beforeEach(async ({ browser }) => {
        page = await browser.newPage();
        uniqueId = generateUniqueId();
        testUsername = `e2e_user_${uniqueId}@karyaksham.com`;

        // 1. Register a new user for test isolation
        await page.goto('/register'); // Navigate directly to register page
        await expect(page).toHaveURL(/.*register/, { timeout: 10000 });

        await page.getByLabel('Email address').fill(testUsername);
        await page.getByLabel('Password', { exact: true }).fill(testPassword);
        await page.getByLabel('Confirm Password').fill(testPassword);
        await page.getByRole('button', { name: 'Register' }).click();

        // Expect successful registration and redirection to login or dashboard
        // If the backend auto-logs in, it goes to dashboard. If not, to login.
        // We'll handle both cases, assuming a success leads to login then dashboard, or directly dashboard.
        if (page.url().includes('login')) { // If redirected to login after register
            await expect(page).toHaveURL(/.*login/, { timeout: 10000 });
            await page.getByLabel('Email address').fill(testUsername);
            await page.getByLabel('Password', { exact: true }).fill(testPassword);
            await page.getByRole('button', { name: 'Login' }).click();
        }

        // Verify user is logged in and redirected to the dashboard (or main app page)
        await expect(page).toHaveURL(/.*dashboard|.*jobs/, { timeout: 15000 }); // Dashboard or job listing page
        // A more robust check: Look for a greeting or user-specific element
        await expect(page.getByText(`Welcome, ${testUsername.split('@')[0]}`)).toBeVisible({ timeout: 10000 });
    });

    test.afterEach(async () => {
        await page.close();
    });

    test('should allow a user to upload a CSV, configure, and monitor a processing job to completion', async () => {
        const jobName = `E2E CSV Filter Job ${uniqueId}`;
        const processingParameters = `filter: Country == "India"\nselect: Name, Country`;

        // 2. Navigate to file upload/job creation page
        await page.getByRole('link', { name: 'New Job' }).click();
        await expect(page).toHaveURL(/.*jobs\/new/, { timeout: 10000 });

        // 3. Upload the dummy CSV file
        const fileInput = page.locator('input[type="file"]');
        await expect(fileInput).toBeEnabled();
        await fileInput.setInputFiles(dummyInputFilePath);

        // Wait for file upload process to complete and UI to show next step (e.g., job configuration form)
        // This might involve waiting for a success message or specific form fields to appear
        await expect(page.getByText('File uploaded successfully!')).toBeVisible({ timeout: 30000 });
        await expect(page.getByLabel('Job Name')).toBeVisible();

        // 4. Configure the job
        await page.getByLabel('Job Name').fill(jobName);
        await page.getByLabel('Processing Parameters').fill(processingParameters);
        await page.getByLabel('Output Format').selectOption('Parquet'); // Assuming 'Parquet' is a valid option

        // 5. Submit the job
        await page.getByRole('button', { name: 'Create Job' }).click();

        // Expect redirection to job details or job list page after submission
        await expect(page).toHaveURL(/.*jobs\/\d+|.*jobs/, { timeout: 10000 });
        await expect(page.getByText(`Job "${jobName}" submitted successfully.`) || page.getByText(`Job "${jobName}" created.`)).toBeVisible();

        // 6. Monitor job status on the job list page
        // Ensure we are on the jobs list page, or navigate there if redirected to job details
        if (!page.url().includes('/jobs')) {
             await page.getByRole('link', { name: 'My Jobs' }).click();
             await expect(page).toHaveURL(/.*jobs/, { timeout: 10000 });
        }

        const jobRow = page.locator(`tr:has-text("${jobName}")`);
        await expect(jobRow).toBeVisible({ timeout: 10000 });

        const statusCell = jobRow.locator('[data-testid="job-status"]'); // Use a data-testid for robustness, or text content if structure is stable

        // Wait for the job status to become 'Completed'
        await test.step('Wait for job to complete', async () => {
            const maxAttempts = 30; // Max 30 attempts * 5 seconds = 150 seconds (2.5 minutes)
            let attempt = 0;
            let currentStatus = '';

            while (currentStatus !== 'Completed' && currentStatus !== 'Failed' && attempt < maxAttempts) {
                currentStatus = await statusCell.textContent() || '';
                console.log(`Job "${jobName}" current status: ${currentStatus}. Attempt ${attempt + 1}/${maxAttempts}.`);
                if (currentStatus === 'Completed' || currentStatus === 'Failed') {
                    break;
                }
                await page.waitForTimeout(5000); // Wait for 5 seconds
                await page.reload(); // Refresh the page to get updated status
                await expect(jobRow).toBeVisible(); // Re-assert row visibility after reload
                attempt++;
            }
            expect(currentStatus).toBe('Completed', `Job "${jobName}" did not complete successfully. Final status: ${currentStatus}`);
        });

        // 7. Verify results download link availability
        const downloadLink = jobRow.getByRole('link', { name: 'Download Result' });
        await expect(downloadLink).toBeVisible();
        // Asserting href structure is good, but exact URL depends on backend/object storage setup
        await expect(downloadLink).toHaveAttribute('href', /.*download\/output\/.+\.parquet/);

        // Optional: Click download link and verify file name (advanced)
        // const [download] = await Promise.all([
        //     page.waitForEvent('download'),
        //     downloadLink.click()
        // ]);
        // expect(download.suggestedFilename()).toMatch(new RegExp(`^${jobName.replace(/ /g, '_')}.+\.parquet$`));
        // // Save the downloaded file for inspection if needed
        // await download.saveAs(path.join(__dirname, `../downloads/${download.suggestedFilename()}`));
    });

    test('should display validation errors for invalid job configuration', async () => {
        const invalidJobName = `Invalid Job ${uniqueId}`;

        await page.getByRole('link', { name: 'New Job' }).click();
        await expect(page).toHaveURL(/.*jobs\/new/, { timeout: 10000 });

        // Upload a file first (required to enable configuration)
        const fileInput = page.locator('input[type="file"]');
        await fileInput.setInputFiles(dummyInputFilePath);
        await expect(page.getByText('File uploaded successfully!')).toBeVisible({ timeout: 30000 });

        await page.getByLabel('Job Name').fill(invalidJobName);
        // Provide invalid processing parameters to trigger a backend validation error
        await page.getByLabel('Processing Parameters').fill(`invalid_syntax: this is not valid config`);
        await page.getByLabel('Output Format').selectOption('Parquet');

        await page.getByRole('button', { name: 'Create Job' }).click();

        // Expect an error message on the UI, indicating validation failure
        // The error message text might vary (e.g., "Invalid input", "Validation failed", "Error parsing parameters")
        await expect(page.getByText(/Failed to create job|Invalid configuration|Syntax error in parameters/i)).toBeVisible({ timeout: 10000 });
        // Ensure the page remains on the job creation form, indicating job was not submitted
        await expect(page).toHaveURL(/.*jobs\/new/);
        // Optionally check for specific field-level error messages
        await expect(page.getByText(/Processing parameters are malformed/i)).toBeVisible();
    });
});