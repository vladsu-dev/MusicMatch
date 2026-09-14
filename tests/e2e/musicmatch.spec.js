import { test, expect } from '@playwright/test';

test('two users register, match, chat, reload and log out', async ({ browser }) => {
  const first = await browser.newContext();
  const second = await browser.newContext();
  const a = await first.newPage();
  const b = await second.newPage();
  const suffix = Date.now();
  const errors = [];
  for (const page of [a,b]) page.on('pageerror', (error) => errors.push(error.message));
  async function register(page, name, email) {
    await page.goto('/');
    await page.getByRole('button', { name: 'Войти', exact: true }).click();
    await page.getByRole('button', { name: 'Регистрация', exact: true }).click();
    await page.getByLabel('Email', { exact: true }).fill(email);
    await page.getByLabel('Пароль', { exact: true }).fill('MusicMatch-e2e-123');
    await page.getByRole('dialog').getByRole('button', { name: 'Зарегистрироваться', exact: true }).click();
    await expect(page.getByRole('heading', { name: 'Заполните анкету' })).toBeVisible();
    await page.getByLabel('Имя', { exact: true }).fill(name);
    // Generate a real PNG in the browser; the UI resizes and converts it to JPEG.
    const png = await page.evaluate(() => {
      const canvas = document.createElement('canvas');
      canvas.width = canvas.height = 20;
      const ctx = canvas.getContext('2d'); ctx.fillStyle = '#d77'; ctx.fillRect(0,0,20,20);
      return canvas.toDataURL('image/png').split(',')[1];
    });
    await page.locator('#profile-photo').setInputFiles({ name: 'photo.png', mimeType: 'image/png', buffer: Buffer.from(png, 'base64') });
    await page.getByRole('button', { name: 'Рок', exact: true }).click();
    await page.getByRole('button', { name: 'Сохранить анкету', exact: true }).click();
    await expect(page.locator('.header-user')).toContainText(name);
  }
  try {
    await register(a, 'Алекс', 'alex' + suffix + '@example.com');
    await register(b, 'Борис', 'boris' + suffix + '@example.com');
    await a.reload();
    await expect(a.locator('.header-user')).toContainText('Алекс');
    await expect(a.locator('.card:not(.behind)')).toContainText('Борис');
    await a.getByRole('button', { name: 'Лайк', exact: true }).click();
    await expect(a.locator('.empty-state')).toBeVisible();
    await b.getByRole('button', { name: 'Лайк', exact: true }).click();
    await expect(b.getByRole('heading', { name: 'Взаимная симпатия' })).toBeVisible();
    await b.getByRole('button', { name: 'Листать дальше' }).click();
    await a.reload();
    for (const page of [a,b]) {
      await page.getByRole('button', { name: /Совпадения/ }).click();
      await page.locator('.match-row').click();
    }
    await a.getByPlaceholder('Написать сообщение...').fill('Привет из MusicMatch!');
    await a.getByRole('button', { name: 'Отправить', exact: true }).click();
    await expect(b.locator('.chat-bubble')).toHaveText('Привет из MusicMatch!');
    await b.reload();
    await b.getByRole('button', { name: /Совпадения/ }).click();
    await b.locator('.match-row').click();
    await expect(b.locator('.chat-bubble')).toHaveText('Привет из MusicMatch!');
    await a.getByRole('button', { name: 'Выйти', exact: true }).click();
    await a.reload();
    await expect(a.getByRole('button', { name: 'Войти', exact: true })).toBeVisible();
    expect(errors).toEqual([]);
  } finally {
    await first.close(); await second.close();
  }
});
