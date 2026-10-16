// @vitest-environment jsdom
import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import StaffPlanner from "../src/pages/StaffPlanner";
import * as api from "../src/api/client";

vi.mock("../src/api/client", () => ({
  default: {get: vi.fn()}, getStoredToken: () => "test-session", setAuthToken: vi.fn(),
  fetchHealth: vi.fn(), fetchLatestSchedule: vi.fn(), listConfigs: vi.fn(), loadConfig: vi.fn(),
  deleteConfig: vi.fn(), exportScheduleExcel: vi.fn(), lookupInvite: vi.fn(), login: vi.fn(),
  runSchedule: vi.fn(), loadScheduleVersion: vi.fn(), saveConfig: vi.fn(), setupUser: vi.fn(),
  friendlyApiError: (_error: unknown, fallback: string) => fallback,
}));

const config: api.ConfigPayload = {
  clinic: {name:"Saved Clinic", timezone:"America/Chicago"}, schedule: {start:"2026-10-19", weeks:1},
  ratios: {patients_per_tech:4, patients_per_rn:12, techs_per_rn:4}, constraints: {},
  bleach: {day:"Thu", rotation:[], cursor:0}, tournament: {trials:10, last_seed:0},
  export_roles:["Tech"], staff:[{id:"saved-tech", name:"Saved Tech", role:"Tech",
    availability:{Mon:false, Tue:true}, pref_open_mwf:2}], demand:[], pto:[],
};

beforeEach(() => {
  vi.resetAllMocks(); localStorage.clear(); sessionStorage.clear();
  vi.mocked(api.default.get).mockResolvedValue({data:{sub:"owner", username:"owner", role:"user"}});
  vi.mocked(api.fetchHealth).mockResolvedValue({status:"ok"});
  vi.mocked(api.fetchLatestSchedule).mockResolvedValue({status:"none"} as any);
  vi.mocked(api.listConfigs).mockResolvedValue(["saved-clinic.json"]);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it("clears an earlier load failure when retry successfully loads the saved staff", async () => {
  vi.mocked(api.loadConfig).mockRejectedValueOnce(new Error("temporary failure")).mockResolvedValue(config);
  render(<StaffPlanner />);
  await screen.findByText("Failed to load config");
  fireEvent.click(screen.getByRole("button", {name:"Load", exact:true}));
  await screen.findByText("Loaded config: saved-clinic.json");
  expect(screen.queryByText("Failed to load config")).toBeNull();
  expect(screen.getByDisplayValue("Saved Tech")).toBeTruthy();
});

it("ignores an older failed request after a newer load succeeds", async () => {
  let rejectOld!: (reason: Error) => void;
  vi.mocked(api.loadConfig).mockReturnValueOnce(new Promise((_resolve, reject) => { rejectOld = reject; }))
    .mockResolvedValue(config);
  render(<StaffPlanner />);
  await waitFor(() => expect(api.loadConfig).toHaveBeenCalledOnce());
  fireEvent.click(screen.getByRole("button", {name:"Load", exact:true}));
  await screen.findByText("Loaded config: saved-clinic.json");
  await act(async () => { rejectOld(new Error("outdated failure")); });
  expect(screen.queryByText("Failed to load config")).toBeNull();
  expect(screen.getByDisplayValue("Saved Tech")).toBeTruthy();
});

it("does not report a successful load as failed when remembering the selection is blocked", async () => {
  vi.mocked(api.loadConfig).mockResolvedValue(config);
  const setItem = Storage.prototype.setItem;
  vi.spyOn(Storage.prototype, "setItem").mockImplementation(function(this: Storage, key, value) {
    if (key === "last_config") throw new Error("browser storage blocked");
    return setItem.call(this, key, value);
  });
  render(<StaffPlanner />);
  await screen.findByText("Loaded config: saved-clinic.json");
  expect(screen.queryByText("Failed to load config")).toBeNull();
  expect(screen.getByDisplayValue("Saved Tech")).toBeTruthy();
});
