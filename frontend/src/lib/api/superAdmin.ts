import { api } from "./client";
import { cleanParams, type PageParams } from "./_params";
import type {
  GenerateInvoicesPayload,
  Page,
  PlatformAnalytics,
  PlatformBillingSummary,
  PlatformInvoice,
  SchoolOverview,
} from "./types";

export interface PlatformInvoiceListParams extends PageParams {
  period?: string;
  status?: string;
}

export const superAdminApi = {
  platformAnalytics: () =>
    api.get("super-admin/analytics/platform").json<PlatformAnalytics>(),

  schoolOverview: (id: string) =>
    api.get(`super-admin/schools/${id}/overview`).json<SchoolOverview>(),

  // Platform billing (platform -> school)
  listPlatformInvoices: (params: PlatformInvoiceListParams = {}) =>
    api
      .get("super-admin/platform-invoices", { searchParams: cleanParams({ ...params }) })
      .json<Page<PlatformInvoice>>(),

  generatePlatformInvoices: (payload: GenerateInvoicesPayload) =>
    api
      .post("super-admin/platform-invoices/generate", { json: payload })
      .json<{ period: string; count: number }>(),

  recordPlatformPayment: (id: string, payload: { amount?: number; receipt_no?: string }) =>
    api
      .post(`super-admin/platform-invoices/${id}/record-payment`, { json: payload })
      .json<PlatformInvoice>(),

  platformBillingSummary: (period?: string) =>
    api
      .get("super-admin/platform-billing/summary", { searchParams: cleanParams({ period }) })
      .json<PlatformBillingSummary>(),
};
