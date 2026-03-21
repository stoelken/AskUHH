'use client'

import * as React from 'react'
import { Slot } from '@radix-ui/react-slot'
import { cva } from 'class-variance-authority'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  'inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0',
  {
    variants: {
      variant: {
        default:
          'border border-[#9aa3af] bg-transparent text-[#d5d9e0] hover:border-[#d5d9e0] hover:bg-[rgba(213,217,224,0.12)]',
        destructive:
          'border border-[rgba(224,102,102,0.45)] bg-[rgba(224,102,102,0.08)] text-[#e06666] hover:bg-[rgba(224,102,102,0.14)]',
        outline:
          'border border-[#363b44] bg-[#2a2e36] text-[#9ba0aa] hover:border-[#9aa3af] hover:text-[#ede9e1]',
        secondary: 'border border-[#363b44] bg-[#2a2e36] text-[#9ba0aa] hover:bg-[#313641]',
        ghost: 'text-[#9ba0aa] hover:bg-[rgba(213,217,224,0.12)] hover:text-[#ede9e1]',
        link: 'text-[#d5d9e0] underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-9 px-4 py-2',
        sm: 'h-8 rounded-md px-3 text-xs',
        lg: 'h-10 rounded-md px-8',
        icon: 'h-9 w-9',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

// Shared button wrapper so variant/size styles stay consistent across the app.
function Button({ className, variant, size, asChild = false, ...props }) {
  const Comp = asChild ? Slot : 'button'
  return <Comp className={cn(buttonVariants({ variant, size, className }))} {...props} />
}

export { Button, buttonVariants }
