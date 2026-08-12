import type { ButtonHTMLAttributes } from 'react'
import { colors, radius, spacing, typography } from './tokens'

type Variant = 'primary' | 'danger' | 'ghost'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
}

const variantStyles: Record<Variant, React.CSSProperties> = {
  primary: { background: colors.primary, color: '#fff', border: 'none' },
  danger: { background: colors.danger, color: '#fff', border: 'none' },
  ghost: { background: 'transparent', color: colors.text, border: `1px solid ${colors.border}` },
}

export function Button({ variant = 'primary', style, ...props }: ButtonProps) {
  return (
    <button
      {...props}
      style={{
        fontFamily: typography.fontFamily,
        fontSize: typography.sizeMd,
        padding: `${spacing.sm} ${spacing.md}`,
        borderRadius: radius.md,
        cursor: 'pointer',
        ...variantStyles[variant],
        ...style,
      }}
    />
  )
}
