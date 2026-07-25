import * as React from "react"

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"

export type DataTableColumn<T> = {
  key: string
  header: React.ReactNode
  cell: (row: T) => React.ReactNode
  className?: string
}

type DataTableProps<T> = {
  columns: Array<DataTableColumn<T>>
  data: T[]
  getRowKey: (row: T) => string
  empty?: React.ReactNode
}

export default function DataTable<T>({ columns, data, getRowKey, empty }: DataTableProps<T>) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          {columns.map((c) => (
            <TableHead key={c.key} className={c.className}>
              {c.header}
            </TableHead>
          ))}
        </TableRow>
      </TableHeader>
      <TableBody>
        {data.map((row) => (
          <TableRow key={getRowKey(row)}>
            {columns.map((c) => (
              <TableCell key={c.key} className={c.className}>
                {c.cell(row)}
              </TableCell>
            ))}
          </TableRow>
        ))}
        {data.length === 0 ? (
          <TableRow>
            <TableCell colSpan={columns.length} className="py-10">
              {empty ?? (
                <div className="text-center text-sm text-muted-foreground">No results.</div>
              )}
            </TableCell>
          </TableRow>
        ) : null}
      </TableBody>
    </Table>
  )
}
