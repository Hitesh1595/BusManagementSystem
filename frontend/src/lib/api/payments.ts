import { api } from "./client";
import { cleanParams, type PageParams } from "./_params";
import type {
  BulkGenerateResult,
  FeeSchedule,
  FeeSchedulePayload,
  FeeScheduleUpdatePayload,
  Invoice,
  InvoiceStatus,
  Page,
  RecordPaymentPayload,
  RecordPaymentResult,
} from "./types";

export interface InvoiceListParams extends PageParams {
  status?: InvoiceStatus;
  student_id?: string;
}

export const paymentsApi = {
  // Fee schedules (admin)
  listFeeSchedules: (params: PageParams = {}) =>
    api
      .get("payments/fee-schedules", { searchParams: cleanParams({ ...params }) })
      .json<Page<FeeSchedule>>(),

  createFeeSchedule: (payload: FeeSchedulePayload) =>
    api.post("payments/fee-schedules", { json: payload }).json<FeeSchedule>(),

  updateFeeSchedule: (id: string, payload: FeeScheduleUpdatePayload) =>
    api.put(`payments/fee-schedules/${id}`, { json: payload }).json<FeeSchedule>(),

  bulkGenerate: (feeScheduleId: string, dueDate?: string) =>
    api
      .post("payments/invoices/bulk-generate", {
        json: { fee_schedule_id: feeScheduleId, due_date: dueDate },
      })
      .json<BulkGenerateResult>(),

  // Invoices (admin sees all; parent sees own)
  listInvoices: (params: InvoiceListParams = {}) =>
    api
      .get("payments/invoices", { searchParams: cleanParams({ ...params }) })
      .json<Page<Invoice>>(),

  getInvoice: (id: string) => api.get(`payments/invoices/${id}`).json<Invoice>(),

  // Manual payment recording (admin)
  recordPayment: (invoiceId: string, payload: RecordPaymentPayload) =>
    api
      .post(`payments/invoices/${invoiceId}/record-payment`, { json: payload })
      .json<RecordPaymentResult>(),
};
