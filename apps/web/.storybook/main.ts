import { fileURLToPath } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import type { StorybookConfig } from '@storybook/react-vite'

const config: StorybookConfig = {
  stories: ['../src/**/*.stories.@(ts|tsx)'],
  addons: [],
  framework: {
    name: '@storybook/react-vite',
    options: {},
  },
  docs: {
    defaultName: 'Docs',
  },
  // Mirrors vite.config.ts's own plugins/alias (Tailwind v4's Vite plugin,
  // the "@" -> src alias) so a component rendered in Storybook looks
  // identical to one rendered in the real app — Storybook's own Vite
  // instance is otherwise completely separate from the app's.
  async viteFinal(viteConfig) {
    const { mergeConfig } = await import('vite')
    return mergeConfig(viteConfig, {
      plugins: [tailwindcss()],
      resolve: {
        alias: {
          '@': fileURLToPath(new URL('../src', import.meta.url)),
        },
      },
    })
  },
}

export default config
