import type { Meta, StoryObj } from '@storybook/react'
import { Button } from './Button'

const meta: Meta<typeof Button> = {
  title: 'Design System/Button',
  component: Button,
  tags: ['autodocs'],
  argTypes: {
    variant: { control: 'select', options: ['primary', 'danger', 'ghost'] },
  },
}
export default meta

type Story = StoryObj<typeof Button>

export const Primary: Story = {
  args: { children: 'Zapisz', variant: 'primary' },
}

export const Danger: Story = {
  args: { children: 'Usuń', variant: 'danger' },
}

export const Ghost: Story = {
  args: { children: 'Anuluj', variant: 'ghost' },
}
