/**
 * TypeScript mirror of the YatraTrack backend contract (FastAPI / Pydantic
 * schemas under /api/v1). Single source of truth for the frontend — feature
 * modules import these rather than redeclaring shapes.
 */

// ---------------------------------------------------------------------------
// Enums (string unions matching backend enums)
// ---------------------------------------------------------------------------

export type Role = "super_admin" | "school_admin" | "driver" | "parent";

export type VehicleType = "bus" | "van" | "minibus" | "car" | "other";

export type ScheduleType = "morning" | "evening" | "both";

export type TransportRequestStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "assigned";

export type TripStatus =
  | "scheduled"
  | "in_progress"
  | "pending_safeguard_check"
  | "completed"
  | "cancelled"
  | "incident";

export type TripSlot = "morning" | "evening";

export type AttendanceStatus = "boarded" | "absent" | "absent_parent_marked";

export type DropType = "stop" | "school";

export type AlertType =
  | "child_not_boarded"
  | "child_not_dropped"
  | "driver_no_show"
  | "sos"
  | "route_deviation"
  | "incident"
  | "insurance_expiry"
  | "driver_behavior_pattern";

export type AlertSeverity = "critical" | "high" | "medium" | "low";

export type NotificationType =
  | "trip_started"
  | "trip_ended"
  | "attendance"
  | "child_not_boarded"
  | "child_not_dropped"
  | "bus_approaching"
  | "broadcast"
  | "alert"
  | "generic";

// ---------------------------------------------------------------------------
// Shared primitives
// ---------------------------------------------------------------------------

export interface LatLng {
  lat: number;
  lng: number;
}

/** Standard paginated list envelope: { items, total, limit, offset }. */
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

/** Error envelope: { error: { code, message, details } }. */
export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

// ---------------------------------------------------------------------------
// Auth / Users
// ---------------------------------------------------------------------------

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  school_id: string | null;
  phone?: string | null;
  notification_prefs?: Record<string, unknown>;
}

/** A user as seen in the admin People screen (list + password reset). */
export interface ManagedUser {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  school_id: string | null;
  phone: string | null;
  is_active: boolean;
}

/** Create a staff account (driver or school_admin). Parents self-register. */
export interface StaffCreatePayload {
  role: "driver" | "school_admin";
  email: string;
  full_name: string;
  phone?: string | null;
  /** super_admin only: which school to create the account in. */
  school_id?: string | null;
}

export interface StaffCreateResult {
  user: ManagedUser;
  temp_password: string;
}

export interface UserUpdatePayload {
  full_name?: string;
  phone?: string | null;
}

export interface TokenResponse {
  access_token: string;
  user: User;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface RegisterPayload {
  join_code: string;
  email: string;
  password: string;
  full_name: string;
  phone?: string;
}

export interface UpdateMePayload {
  full_name?: string;
  phone?: string;
  notification_prefs?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Schools
// ---------------------------------------------------------------------------

export interface SchoolSettings {
  driver_phone_visible?: boolean;
  trip_autogen_enabled?: boolean;
  /** Distance (metres) from a stop that triggers a `bus_approaching` alert. */
  bus_approaching_radius_m?: number;
  [key: string]: unknown;
}

export interface School {
  id: string;
  name: string;
  address: string | null;
  phone: string | null;
  email: string | null;
  logo_url: string | null;
  timezone: string;
  school_location: LatLng | null;
  join_code: string;
  settings: SchoolSettings;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SchoolUpdatePayload {
  name?: string;
  address?: string;
  phone?: string;
  email?: string;
  logo_url?: string;
  timezone?: string;
  school_location?: LatLng | null;
}

/** super_admin school creation (POST /schools/). */
export interface SchoolCreatePayload {
  name: string;
  address?: string | null;
  phone?: string | null;
  email?: string | null;
  timezone?: string;
}

// ---------------------------------------------------------------------------
// Vehicles & Drivers
// ---------------------------------------------------------------------------

export interface Vehicle {
  id: string;
  school_id: string;
  plate_number: string;
  vehicle_type: VehicleType;
  capacity: number;
  make: string | null;
  model: string | null;
  year: number | null;
  insurance_expiry: string | null;
  fitness_expiry: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface VehiclePayload {
  plate_number: string;
  vehicle_type?: VehicleType;
  capacity: number;
  make?: string | null;
  model?: string | null;
  year?: number | null;
  insurance_expiry?: string | null;
  fitness_expiry?: string | null;
  is_active?: boolean;
}

export interface Driver {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  role: "driver";
  school_id: string | null;
  is_active: boolean;
  created_at: string;
}

export interface DriverCreatePayload {
  email: string;
  full_name: string;
  phone?: string;
}

export interface DriverCreateResult {
  driver: Driver;
  temp_password: string;
}

export interface DriverUpdatePayload {
  full_name?: string;
  phone?: string;
  is_active?: boolean;
}

// ---------------------------------------------------------------------------
// Routes & Stops
// ---------------------------------------------------------------------------

export interface Stop {
  id: string;
  route_id: string;
  name: string;
  location: LatLng;
  address: string | null;
  stop_order: number;
  arrival_time: string | null;
  created_at: string;
}

export interface Route {
  id: string;
  school_id: string;
  name: string;
  description: string | null;
  vehicle_id: string | null;
  driver_id: string | null;
  schedule_type: ScheduleType;
  version: number;
  is_active: boolean;
  has_route_path: boolean;
  stops: Stop[];
  created_at: string;
  updated_at: string;
}

export interface RouteCreatePayload {
  name: string;
  description?: string | null;
  schedule_type?: ScheduleType;
  vehicle_id?: string | null;
  driver_id?: string | null;
}

export interface RouteUpdatePayload {
  name?: string;
  description?: string | null;
  schedule_type?: ScheduleType;
  vehicle_id?: string | null;
  driver_id?: string | null;
  is_active?: boolean;
  /** Required for optimistic locking; server returns 409 if stale. */
  version: number;
}

export interface StopCreatePayload {
  name: string;
  location: LatLng;
  address?: string | null;
  stop_order?: number;
  arrival_time?: string | null;
}

export interface StopUpdatePayload {
  name?: string;
  location?: LatLng;
  address?: string | null;
  arrival_time?: string | null;
}

// ---------------------------------------------------------------------------
// Students, Assignments & Transport Requests
// ---------------------------------------------------------------------------

export interface Student {
  id: string;
  school_id: string;
  parent_id: string;
  full_name: string;
  grade: string | null;
  section: string | null;
  pickup_address: string | null;
  pickup_location: LatLng | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface StudentCreatePayload {
  full_name: string;
  grade?: string | null;
  section?: string | null;
  pickup_address?: string | null;
  pickup_location?: LatLng | null;
}

export interface StudentUpdatePayload extends Partial<StudentCreatePayload> {
  is_active?: boolean;
}

export interface StudentRouteAssignment {
  id: string;
  school_id: string;
  student_id: string;
  route_id: string;
  stop_id: string;
  assigned_at: string;
  is_active: boolean;
}

export interface StopSuggestion {
  stop_id: string;
  route_id: string;
  name: string;
  distance_m: number;
  arrival_time: string | null;
}

export interface TransportRequest {
  id: string;
  school_id: string;
  parent_id: string;
  student_id: string;
  pickup_address: string | null;
  pickup_location: LatLng | null;
  status: TransportRequestStatus;
  assigned_route_id: string | null;
  assigned_stop_id: string | null;
  admin_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface TransportRequestCreatePayload {
  student_id: string;
  pickup_address?: string | null;
  pickup_location?: LatLng | null;
}

export interface TransportRequestUpdatePayload {
  status: TransportRequestStatus;
  assigned_route_id?: string | null;
  assigned_stop_id?: string | null;
  admin_notes?: string | null;
}

// ---------------------------------------------------------------------------
// Trips & Tracking
// ---------------------------------------------------------------------------

export interface Trip {
  id: string;
  school_id: string;
  route_id: string;
  driver_id: string;
  vehicle_id: string;
  status: TripStatus;
  scheduled_date: string;
  scheduled_departure_at: string;
  slot: TripSlot;
  current_stop_order: number | null;
  started_at: string | null;
  ended_at: string | null;
  safeguarding_checked: boolean;
  original_driver_id: string | null;
  reassigned_at: string | null;
  reassignment_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface RouteBrief {
  id: string;
  name: string;
  schedule_type: ScheduleType;
}

export interface VehicleBrief {
  id: string;
  plate_number: string;
}

export interface DriverBrief {
  id: string;
  full_name: string;
  /** Disclosed only for parent role during in_progress trip when permitted. */
  phone?: string | null;
}

export interface TripDetail extends Trip {
  route: RouteBrief | null;
  vehicle: VehicleBrief | null;
  driver: DriverBrief | null;
}

export interface TripCreatePayload {
  route_id: string;
  scheduled_date: string;
  slot: TripSlot;
}

export interface GenerateResult {
  created: number;
}

export interface AttendanceRecord {
  student_id: string;
  student_name: string;
  stop_id: string | null;
  /** null = not yet scanned/marked. */
  status: AttendanceStatus | null;
  marked_at: string | null;
}

export interface AttendanceInput {
  student_id: string;
  status: AttendanceStatus;
}

export interface AttendanceResult {
  processed: number;
  alerts_triggered: number;
}

export interface DropPayload {
  student_ids: string[];
  drop_type: DropType;
  stop_id?: string;
}

export interface DropResult {
  dropped: number;
}

export interface EndTripResult {
  status: "completed" | "pending_safeguard_check";
  unresolved_students: string[];
}

export interface AbsentMarkResult {
  student_id: string;
  status: "absent_parent_marked" | "cancelled";
}

export interface AbsenceListItem {
  student_id: string;
  student_name: string;
  stop_id: string | null;
  marked_at: string;
}

export interface GpsLogGeoJSON {
  type: "Feature";
  geometry: {
    type: "LineString";
    coordinates: [number, number][]; // [lng, lat]
  };
  properties: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Alerts
// ---------------------------------------------------------------------------

export interface Alert {
  id: string;
  school_id: string;
  trip_id: string | null;
  type: AlertType;
  severity: AlertSeverity;
  title: string;
  description: string | null;
  triggered_by: string | null;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  resolved_at: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
}

/** Alerts list uses { items, total } (no limit/offset echo). */
export interface AlertListResponse {
  items: Alert[];
  total: number;
}

export interface AlertAckResult {
  id: string;
  acknowledged: boolean;
}

export interface AlertResolveResult {
  id: string;
  resolved: boolean;
  trip_completed: boolean;
}

// ---------------------------------------------------------------------------
// Notifications
// ---------------------------------------------------------------------------

export interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  body: string | null;
  data: Record<string, unknown>;
  is_read: boolean;
  read_at: string | null;
  created_at: string;
}

/** Notifications list shape: { notifications, total, page, page_size }. */
export interface NotificationListResponse {
  notifications: Notification[];
  total: number;
  page: number;
  page_size: number;
}
