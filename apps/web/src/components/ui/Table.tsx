import type { ComponentProps } from 'react'
import { cx } from '@/lib/cx'

/** A table that scrolls sideways inside its own box, so the page itself never scrolls horizontally on a phone. */
export function Table({ className, ...props }: ComponentProps<'table'>) {
  return (
    <div className="table-wrap">
      <table className={cx('table', className)} {...props} />
    </div>
  )
}
