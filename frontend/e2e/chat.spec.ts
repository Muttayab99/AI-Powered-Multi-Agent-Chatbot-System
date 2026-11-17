import AxeBuilder from '@axe-core/playwright'
import { expect, test } from '@playwright/test'

const openTools = async (page: import('@playwright/test').Page, isMobile: boolean) => {
  if (isMobile) await page.getByRole('button', { name: 'Open chat tools' }).click()
}

test('runs Python through the router and shows the agent', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { name: 'What can I help with?' })).toBeVisible()

  await page.getByRole('textbox', { name: 'Message' }).fill('Execute this Python code:\nprint(6 * 7)')
  await page.keyboard.press('Enter')

  const log = page.getByRole('log', { name: 'Conversation' })
  const reply = log.locator('article').last()
  await expect(reply).toContainText('42')
  await expect(reply).toContainText('Python')
})

test('uploads a document, shows it as context, and New chat clears it', async ({ page, isMobile }) => {
  test.setTimeout(300_000)
  await page.goto('/')
  const text = 'Filler sentence. '.repeat(40) + 'The project budget for 2025 is 42 million dollars. ' + 'More filler. '.repeat(40)

  await page.locator('input[type=file]').first().setInputFiles({
    name: 'report.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from(text),
  })
  const log = page.getByRole('log', { name: 'Conversation' })
  await expect(log).toContainText('Reading report.txt')
  // A fresh gateway loads the embedding model on the first upload, which can take a few minutes.
  await expect(log).toContainText("Loaded 'report.txt'", { timeout: 240_000 })

  await openTools(page, isMobile)
  const tools = isMobile ? page.getByRole('dialog') : page.getByRole('complementary', { name: 'Chat tools' })
  await expect(tools.getByText('report.txt')).toBeVisible()

  await tools.getByRole('button', { name: 'New chat' }).click()
  await expect(tools.getByText('Nothing loaded yet')).toBeVisible()
  if (isMobile) await page.keyboard.press('Escape')
  await expect(page.getByRole('heading', { name: 'What can I help with?' })).toBeVisible()
})

for (const theme of ['light', 'dark'] as const) {
  test(`has no serious accessibility issues (${theme})`, async ({ page }) => {
    await page.addInitScript((t) => localStorage.setItem('chatbot.theme', t), theme)
    await page.goto('/')
    await expect(page.getByRole('heading', { name: 'What can I help with?' })).toBeVisible()
    const results = await new AxeBuilder({ page }).withTags(['wcag2a', 'wcag2aa', 'wcag21aa']).analyze()
    const serious = results.violations.filter((v) => v.impact === 'serious' || v.impact === 'critical')
    expect(serious.map((v) => `${v.id}: ${v.nodes.map((n) => n.target.join(' ')).join(', ')}`)).toEqual([])

    // Nothing may be wider than the viewport (no sideways scrolling on phones).
    const overflowing = await page.evaluate(() =>
      [...document.querySelectorAll('main *')]
        .filter((el) => el.getBoundingClientRect().right > window.innerWidth + 1)
        .map((el) => el.tagName.toLowerCase() + (el.className ? `.${String(el.className).split(' ')[0]}` : '')),
    )
    expect(overflowing).toEqual([])
    await page.screenshot({ path: `test-results/screens/${test.info().project.name}-${theme}.png` })
  })
}
