/**
 * Data table capture component for bulk structured input.
 */

import { useMemo, useState } from 'react';
import type {
  DataTableColumn,
  DataTableRow,
  DataTableSubmission,
} from '../../types/design-session';

interface DataTableCaptureProps {
  title: string;
  columns: DataTableColumn[];
  minRows?: number;
  starterRows?: number;
  inputModes?: Array<'paste' | 'inline' | 'import'>;
  summaryPrompt?: string;
  onSubmit: (payload: DataTableSubmission) => void;
}

const MAX_ROWS = 50;

function buildEmptyRow(columns: DataTableColumn[]): DataTableRow {
  return columns.reduce<DataTableRow>((row, column) => {
    row[column.name] = '';
    return row;
  }, {});
}

function normalizeRows(rows: DataTableRow[], columns: DataTableColumn[]): DataTableRow[] {
  return rows.filter((row) =>
    columns.some((column) => (row[column.name] || '').trim().length > 0)
  );
}

function parsePastedRows(text: string, columns: DataTableColumn[]): DataTableRow[] {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (!lines.length) return [];

  const delimiter = text.includes('\t') ? '\t' : ',';
  const parsed = lines.map((line) => line.split(delimiter).map((cell) => cell.trim()));

  return parsed.slice(0, MAX_ROWS).map((cells) => {
    const row = buildEmptyRow(columns);
    columns.forEach((column, idx) => {
      row[column.name] = cells[idx] ?? '';
    });
    return row;
  });
}

export function DataTableCapture({
  title,
  columns,
  minRows = 1,
  starterRows = 1,
  inputModes = ['paste', 'inline'],
  summaryPrompt,
  onSubmit,
}: DataTableCaptureProps) {
  const initialRows = useMemo(
    () =>
      Array.from({ length: Math.min(MAX_ROWS, Math.max(1, starterRows)) }).map(() =>
        buildEmptyRow(columns)
      ),
    [columns, starterRows]
  );

  const [rows, setRows] = useState<DataTableRow[]>(initialRows);
  const [pasteValue, setPasteValue] = useState('');
  const [error, setError] = useState<string | null>(null);

  const handleCellChange = (rowIndex: number, columnName: string, value: string) => {
    setRows((prev) =>
      prev.map((row, idx) =>
        idx === rowIndex ? { ...row, [columnName]: value } : row
      )
    );
  };

  const handleAddRow = () => {
    setRows((prev) =>
      prev.length >= MAX_ROWS ? prev : [...prev, buildEmptyRow(columns)]
    );
  };

  const handleRemoveRow = (rowIndex: number) => {
    setRows((prev) => prev.filter((_, idx) => idx !== rowIndex));
  };

  const handlePasteParse = () => {
    const parsedRows = parsePastedRows(pasteValue, columns);
    if (!parsedRows.length) {
      setError('Paste data with one row per line.');
      return;
    }
    setError(null);
    setRows(parsedRows);
  };

  const handleSubmit = () => {
    const cleanedRows = normalizeRows(rows, columns);
    if (cleanedRows.length < minRows) {
      setError(`Add at least ${minRows} rows.`);
      return;
    }

    const missingRequired = columns
      .filter((column) => column.required)
      .some((column) =>
        cleanedRows.some((row) => !(row[column.name] || '').trim())
      );

    if (missingRequired) {
      setError('Fill all required fields before submitting.');
      return;
    }

    setError(null);
    onSubmit({
      title,
      columns,
      rows: cleanedRows,
    });
  };

  return (
    <div className="mt-4 space-y-4">
      <div>
        <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
        {summaryPrompt && (
          <p className="text-xs text-gray-500 mt-1">{summaryPrompt}</p>
        )}
      </div>

      {inputModes.includes('paste') && (
        <div className="rounded-lg border border-gray-200 bg-white p-3">
          <label className="text-xs font-medium text-gray-600">
            Paste rows from a spreadsheet
          </label>
          <textarea
            value={pasteValue}
            onChange={(event) => setPasteValue(event.target.value)}
            rows={3}
            placeholder="Paste rows here (tab or comma separated)"
            className="mt-2 w-full rounded-md border border-gray-200 p-2 text-xs focus:border-blue-300 focus:outline-none"
          />
          <div className="mt-2 flex justify-end">
            <button
              type="button"
              onClick={handlePasteParse}
              className="rounded-md border border-blue-200 px-3 py-1 text-xs text-blue-600 hover:bg-blue-50"
            >
              Parse rows
            </button>
          </div>
        </div>
      )}

      <div className="overflow-x-auto rounded-lg border border-gray-200 bg-white">
        <table className="min-w-full text-xs">
          <thead className="bg-gray-50 text-gray-500">
            <tr>
              {columns.map((column) => (
                <th key={column.name} className="px-3 py-2 text-left font-medium">
                  {column.name}
                  {column.required && <span className="text-red-400"> *</span>}
                </th>
              ))}
              <th className="px-3 py-2 text-right font-medium text-gray-400">Remove</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={`${rowIndex}`} className="border-t border-gray-100">
                {columns.map((column) => {
                  const value = row[column.name] || '';
                  if (column.type === 'enum' && column.options?.length) {
                    return (
                      <td key={column.name} className="px-3 py-2">
                        <select
                          value={value}
                          onChange={(event) =>
                            handleCellChange(rowIndex, column.name, event.target.value)
                          }
                          className="w-full rounded-md border border-gray-200 p-1 text-xs focus:border-blue-300 focus:outline-none"
                        >
                          <option value="">Select</option>
                          {column.options.map((option) => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                          ))}
                        </select>
                      </td>
                    );
                  }

                  const inputType =
                    column.type === 'number'
                      ? 'number'
                      : column.type === 'date'
                        ? 'date'
                        : column.type === 'url'
                          ? 'url'
                          : 'text';

                  return (
                    <td key={column.name} className="px-3 py-2">
                      <input
                        type={inputType}
                        value={value}
                        onChange={(event) =>
                          handleCellChange(rowIndex, column.name, event.target.value)
                        }
                        className="w-full rounded-md border border-gray-200 p-1 text-xs focus:border-blue-300 focus:outline-none"
                      />
                    </td>
                  );
                })}
                <td className="px-3 py-2 text-right">
                  <button
                    type="button"
                    onClick={() => handleRemoveRow(rowIndex)}
                    className="text-xs text-gray-400 hover:text-red-500"
                  >
                    Remove
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
        <button
          type="button"
          onClick={handleAddRow}
          className="rounded-md border border-gray-200 px-3 py-1 text-xs text-gray-600 hover:bg-gray-50"
        >
          Add row
        </button>
        <div className="flex items-center gap-3">
          {error && <span className="text-xs text-red-500">{error}</span>}
          <button
            type="button"
            onClick={handleSubmit}
            className="rounded-md bg-blue-600 px-4 py-1 text-xs text-white hover:bg-blue-700"
          >
            Submit table
          </button>
        </div>
      </div>
    </div>
  );
}
