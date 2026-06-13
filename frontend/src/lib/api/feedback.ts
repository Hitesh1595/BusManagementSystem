import { api } from "./client";
import { cleanParams, type PageParams } from "./_params";
import type {
  DriverRating,
  FeedbackCreatePayload,
  FeedbackReviewPayload,
  Page,
  TripFeedback,
} from "./types";

export interface FeedbackListParams extends PageParams {
  /** Only flagged (rating <= 2 or admin-flagged) feedback. */
  flagged?: boolean;
  /** Restrict to one driver. */
  driver_id?: string;
}

export const feedbackApi = {
  /** Parent rates a completed trip. */
  submit: (tripId: string, payload: FeedbackCreatePayload) =>
    api.post(`trips/${tripId}/feedback`, { json: payload }).json<TripFeedback>(),

  /** Admin: list feedback (full text). */
  list: (params: FeedbackListParams = {}) =>
    api
      .get("feedback", { searchParams: cleanParams({ ...params }) })
      .json<Page<TripFeedback>>(),

  /** Admin: mark reviewed / adjust flag + notes. */
  review: (id: string, payload: FeedbackReviewPayload) =>
    api.put(`feedback/${id}/review`, { json: payload }).json<TripFeedback>(),

  /** Driver: aggregate of own feedback only (OQ-15). */
  myRating: () => api.get("feedback/my-rating").json<DriverRating>(),
};
