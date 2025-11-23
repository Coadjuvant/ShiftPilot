export type StaffRow = {
  id: string;
  name: string;
  role: string;
  can_bleach?: boolean;
  can_open?: boolean;
  can_close?: boolean;
  availability?: Record<string, boolean>;
  pref_open_mwf?: number;
  pref_open_tts?: number;
  pref_mid_mwf?: number;
  pref_mid_tts?: number;
  pref_close_mwf?: number;
  pref_close_tts?: number;
};

export type DemandRow = {
  Day: string;
  Patients: number;
  Tech_Open: number;
  Tech_Mid: number;
  Tech_Close: number;
  RN_Count: number;
  Admin_Count: number;
};

export type PTORow = {
  staff_id: string;
  start_date: string;
  end_date: string;
};
