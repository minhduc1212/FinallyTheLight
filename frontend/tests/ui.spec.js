import { test, expect } from '@playwright/test';

test.describe('Finally The Light — UI Tests', () => {
  
  test('Landing Page renders and redirects to dashboard', async ({ page }) => {
    await page.goto('/');
    
    // Verify wordmark is visible
    await expect(page.locator('.wordmark')).toHaveText('Finally The Light');
    
    // Verify hero section is visible
    await expect(page.locator('.hero-title')).toContainText('Dịch truyện, giữ trọn văn phong.');
    
    // Clicking main CTA button should navigate to dashboard
    await page.click('text=Bắt đầu dịch');
    await expect(page).toHaveURL(/.*\/dashboard/);
  });

  test('Dashboard / Projects - empty state and project creation', async ({ page }) => {
    // Intercept projects list to return empty initially
    let projectsList = [];
    await page.route('**/api/projects', async (route) => {
      if (route.request().method() === 'GET') {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(projectsList),
        });
      }
    });

    // Intercept project status and novel list fetches
    await page.route('**/api/projects/*/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ status: 'idle', current_chunk: 0, total_chunks: 0, step: 'Idle' }),
      });
    });

    await page.route('**/api/projects/*/novels', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([]),
      });
    });

    // Intercept project creation (POST)
    await page.route('**/api/projects/*', async (route) => {
      if (route.request().method() === 'POST') {
        const url = route.request().url();
        const projectName = decodeURIComponent(url.split('/').pop() || '');
        
        if (!/^[a-zA-Z0-9_-]+$/.test(projectName)) {
          await route.fulfill({
            status: 400,
            contentType: 'application/json',
            body: JSON.stringify({ detail: 'Tên dự án không hợp lệ. Chỉ chấp nhận chữ cái, số, gạch dưới và gạch ngang.' }),
          });
        } else {
          projectsList.push(projectName);
          await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({ message: 'Project created' }),
          });
        }
      }
    });

    await page.goto('/#/dashboard/projects');

    // Verify empty state is displayed
    await expect(page.locator('.table-empty-state')).toContainText('Chưa có dự án nào. Hãy tạo dự án mới để bắt đầu.');

    // Attempt to create a project with invalid name containing space
    await page.fill('input[placeholder="Tên dự án mới…"]', 'My Project Space');
    
    // Capture browser alert dialog
    let alertMsg = '';
    page.once('dialog', async (dialog) => {
      alertMsg = dialog.message();
      await dialog.accept();
    });
    
    await page.click('button:has-text("Thêm Dự án")');
    
    // Wait briefly and verify alert text matches our backend validation
    await page.waitForTimeout(500);
    expect(alertMsg).toContain('Tên dự án không hợp lệ');

    // Create a project with valid name
    await page.fill('input[placeholder="Tên dự án mới…"]', 'TestProject');
    await page.click('button:has-text("Thêm Dự án")');

    // Verify project name appears in the table
    await expect(page.locator('.project-link')).toHaveText('TestProject');
  });

  test('Project Detail - novels list and details', async ({ page }) => {
    // Intercept project detail calls
    await page.route('**/api/projects/TestProject/novels', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(['chualam.txt']),
      });
    });

    await page.route('**/api/projects/TestProject/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'idle',
          current_chunk: 0,
          total_chunks: 0,
          step: 'Idle',
        }),
      });
    });

    await page.goto('/#/dashboard/TestProject');

    // Verify header and project title
    await expect(page.locator('.page-header h2')).toContainText('Tiểu thuyết');
    await expect(page.locator('.subtitle')).toContainText('— TestProject');

    // Verify novel file name is listed in the table
    await expect(page.locator('.novel-link')).toHaveText('chualam.txt');
  });

  test('Novel Chunks / Translation - Checkpoints and custom controls', async ({ page }) => {
    // Intercept configuration calls
    await page.route('**/api/genres', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          genres: { default: { label: 'Mặc định' } },
          languages: { vi: { name: 'Tiếng Việt' } }
        }),
      });
    });

    // Intercept chunks list
    await page.route('**/api/projects/TestProject/novels/chualam.txt/chunks*', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          total_chunks: 2,
          page: 1,
          limit: 50,
          chunks: [
            { id: 0, original: 'Original text one', translated: 'Bản dịch một', status: 'completed' },
            { id: 1, original: 'Original text two', translated: '', status: 'pending' }
          ],
        }),
      });
    });

    // Mock checkpoints to return a match for 'chualam'
    await page.route('**/api/projects/TestProject/checkpoints', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify([
          { file_stem: 'chualam', current_chunk: 1, total_chunks: 2 }
        ]),
      });
    });

    // Intercept status to return idle
    await page.route('**/api/projects/TestProject/status', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          status: 'idle',
          current_chunk: 1,
          total_chunks: 2,
          step: 'Idle',
          output_file: null
        }),
      });
    });

    // Intercept HEAD request to check download file exists
    await page.route('**/api/projects/TestProject/download/chualam_vi.txt', async (route) => {
      if (route.request().method() === 'HEAD') {
        await route.fulfill({ status: 200 });
      }
    });

    await page.goto('/#/dashboard/TestProject/novels/chualam.txt');

    // Verify novel title in header
    await expect(page.locator('h3')).toContainText('Dịch: chualam.txt');

    // Check that custom resume and fresh start buttons exist
    await expect(page.locator('button:has-text("Dịch Tiếp")')).toBeVisible();
    await expect(page.locator('button:has-text("Dịch Mới")')).toBeVisible();

    // Verify that the download button is enabled since checkDownloadAvailable returns 200
    const downloadBtn = page.locator('button:has-text("Tải Bản Dịch")');
    await expect(downloadBtn).not.toBeDisabled();
    
    // Verify table records are rendered correctly
    await expect(page.locator('td:has-text("#1")')).toBeVisible();
    await expect(page.locator('td:has-text("#2")')).toBeVisible();
  });
});
